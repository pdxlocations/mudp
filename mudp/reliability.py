from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
import time

from meshtastic import BROADCAST_NUM, mesh_pb2, portnums_pb2
from mudp.singleton import conn, node
from pubsub import pub

NUM_RELIABLE_RETX = 3
RETRY_POLL_INTERVAL_SEC = 0.05
UDP_SLOT_TIME_MSEC = 40
UDP_PROCESSING_TIME_MSEC = 500
UDP_CWMIN = 3
UDP_CWMAX = 8
UDP_MIN_PACKET_AIRTIME_MSEC = 80
UDP_AIRTIME_PER_BYTE_MSEC = 8


def parse_node_id(node_id: str | int) -> int:
    if isinstance(node_id, int):
        return node_id
    text = str(node_id).strip()
    if text.startswith("!"):
        text = text[1:]
    return int(text, 16)


def is_direct_message(packet: mesh_pb2.MeshPacket) -> bool:
    return int(getattr(packet, "to", BROADCAST_NUM)) != BROADCAST_NUM


def is_text_message(packet: mesh_pb2.MeshPacket) -> bool:
    if not packet.HasField("decoded"):
        return False
    return packet.decoded.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP


def compute_reply_hop_limit(packet: mesh_pb2.MeshPacket, default_hop_limit: int = 3) -> int:
    hop_limit = int(getattr(packet, "hop_limit", 0) or 0)
    hop_start = int(getattr(packet, "hop_start", 0) or 0)
    configured = int(hop_start or default_hop_limit or hop_limit or 3)
    hops_used = max(hop_start - hop_limit, 0)
    if hops_used > configured:
        return hops_used
    if hop_start == 0:
        return 0
    if hops_used + 2 < configured:
        return hops_used + 2
    return configured


def should_ack_with_want_ack(packet: mesh_pb2.MeshPacket) -> bool:
    return bool(
        getattr(packet, "want_ack", False)
        and is_direct_message(packet)
        and is_text_message(packet)
        and int(getattr(packet, "to", BROADCAST_NUM)) == parse_node_id(node.node_id)
    )


def build_routing_ack_data(
    *,
    request_id: int,
    error_reason: mesh_pb2.Routing.Error.ValueType = mesh_pb2.Routing.Error.NONE,
) -> mesh_pb2.Data:
    routing = mesh_pb2.Routing()
    routing.error_reason = error_reason

    data = mesh_pb2.Data()
    data.portnum = portnums_pb2.PortNum.ROUTING_APP
    data.payload = routing.SerializeToString()
    data.request_id = int(request_id)
    return data


def parse_routing(packet: mesh_pb2.MeshPacket) -> mesh_pb2.Routing | None:
    if not packet.HasField("decoded"):
        return None
    if packet.decoded.portnum != portnums_pb2.PortNum.ROUTING_APP:
        return None
    routing = mesh_pb2.Routing()
    try:
        routing.ParseFromString(packet.decoded.payload)
    except Exception:
        return None
    return routing


def is_ack(packet: mesh_pb2.MeshPacket) -> bool:
    routing = parse_routing(packet)
    if routing is None or not packet.HasField("decoded") or not packet.decoded.request_id:
        return False

    # Some Meshtastic ACKs arrive with a request_id but without an explicit
    # routing variant set. Treat those empty routing payloads as ACKs.
    variant = routing.WhichOneof("variant")
    if variant is None:
        return True

    return bool(
        variant == "error_reason" and routing.error_reason == mesh_pb2.Routing.Error.NONE
    )


def is_nak(packet: mesh_pb2.MeshPacket) -> bool:
    routing = parse_routing(packet)
    if routing is None or not packet.HasField("decoded") or not packet.decoded.request_id:
        return False
    return bool(
        routing.WhichOneof("variant") == "error_reason" and routing.error_reason != mesh_pb2.Routing.Error.NONE
    )


def compute_retransmission_delay_msec(raw_size: int) -> int:
    packet_airtime = max(UDP_MIN_PACKET_AIRTIME_MSEC, int(raw_size) * UDP_AIRTIME_PER_BYTE_MSEC)
    contention = (
        (2 ** UDP_CWMIN)
        + (2 * UDP_CWMAX)
        + (2 ** int((UDP_CWMAX + UDP_CWMIN) / 2))
    ) * UDP_SLOT_TIME_MSEC
    return int((2 * packet_airtime) + contention + UDP_PROCESSING_TIME_MSEC)


@dataclass
class PendingAck:
    packet_id: int
    destination: int
    created_at: float
    raw_bytes: bytes
    retries_left: int
    next_retry_monotonic: float
    addr: tuple[str, int]


class PendingAckRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: dict[int, PendingAck] = {}
        self._wake = Event()
        self._worker: Thread | None = None

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = Thread(target=self._run, name="mudp-retry-loop", daemon=True)
            self._worker.start()

    def _run(self) -> None:
        while True:
            self.process_due()
            self._wake.wait(RETRY_POLL_INTERVAL_SEC)
            self._wake.clear()

    def track(
        self,
        packet_id: int,
        destination: int,
        created_at: float,
        raw_bytes: bytes,
        addr: tuple[str, int],
    ) -> None:
        now = time.monotonic()
        delay_sec = compute_retransmission_delay_msec(len(raw_bytes)) / 1000.0
        with self._lock:
            self._pending[int(packet_id)] = PendingAck(
                packet_id=int(packet_id),
                destination=int(destination),
                created_at=float(created_at),
                raw_bytes=bytes(raw_bytes),
                retries_left=NUM_RELIABLE_RETX - 1,
                next_retry_monotonic=now + delay_sec,
                addr=addr,
            )
        self._ensure_worker()
        self._wake.set()

    def resolve(self, request_id: int) -> PendingAck | None:
        with self._lock:
            return self._pending.pop(int(request_id), None)

    def get(self, request_id: int) -> PendingAck | None:
        with self._lock:
            return self._pending.get(int(request_id))

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()
        self._wake.set()

    def process_due(self, now: float | None = None) -> None:
        check_time = time.monotonic() if now is None else float(now)
        retries: list[PendingAck] = []
        failures: list[PendingAck] = []

        with self._lock:
            for packet_id, pending in list(self._pending.items()):
                if pending.next_retry_monotonic > check_time:
                    continue
                if pending.retries_left <= 0:
                    self._pending.pop(packet_id, None)
                    failures.append(pending)
                    continue
                pending.retries_left -= 1
                pending.next_retry_monotonic = check_time + (
                    compute_retransmission_delay_msec(len(pending.raw_bytes)) / 1000.0
                )
                retries.append(pending)

        for pending in retries:
            try:
                conn.sendto(pending.raw_bytes, pending.addr)
                pub.sendMessage("mesh.tx.retry", pending=pending)
            except Exception as error:
                pub.sendMessage("mesh.tx.retry_error", pending=pending, error=error)

        for pending in failures:
            pub.sendMessage(
                "mesh.tx.max_retransmit",
                pending=pending,
                error_reason=mesh_pb2.Routing.Error.MAX_RETRANSMIT,
            )


pending_acks = PendingAckRegistry()


def register_pending_ack(packet: mesh_pb2.MeshPacket, raw_bytes: bytes) -> None:
    if not getattr(packet, "want_ack", False):
        return
    destination = int(getattr(packet, "to", BROADCAST_NUM))
    if destination == BROADCAST_NUM:
        return
    if not conn.host or not conn.port:
        return
    pending_acks.track(
        packet_id=int(packet.id),
        destination=destination,
        created_at=time.time(),
        raw_bytes=raw_bytes,
        addr=(str(conn.host), int(conn.port)),
    )


def send_ack(
    request_packet: mesh_pb2.MeshPacket,
    *,
    error_reason: mesh_pb2.Routing.Error.ValueType = mesh_pb2.Routing.Error.NONE,
    want_ack: bool | None = None,
    hop_limit: int | None = None,
    packet_id: int | None = None,
) -> mesh_pb2.MeshPacket:
    from mudp.tx_message_handler import build_mesh_packet

    resolved_hop_limit = int(
        compute_reply_hop_limit(request_packet) if hop_limit is None else hop_limit
    )
    packet = build_mesh_packet(
        build_routing_ack_data(
            request_id=int(getattr(request_packet, "id")),
            error_reason=error_reason,
        ),
        to=int(getattr(request_packet, "from")),
        want_ack=should_ack_with_want_ack(request_packet) if want_ack is None else bool(want_ack),
        hop_limit=resolved_hop_limit,
        hop_start=resolved_hop_limit,
        packet_id=packet_id,
    )
    packet.priority = mesh_pb2.MeshPacket.Priority.ACK
    return packet


def publish_ack(packet: mesh_pb2.MeshPacket) -> None:
    raw_bytes = packet.SerializeToString()
    register_pending_ack(packet, raw_bytes)
    conn.sendto(raw_bytes, (conn.host, conn.port))
