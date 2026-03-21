from collections import OrderedDict
import time
from typing import Optional

import threading
import select
from google.protobuf.message import DecodeError
from pubsub import pub

from meshtastic import protocols
from meshtastic.protobuf import portnums_pb2, mesh_pb2
from mudp.reliability import is_ack, is_nak, parse_routing, pending_acks
from mudp.singleton import conn
from mudp.encryption import decrypt_packet


def _decode_and_optionally_parse(
    raw: bytes, key: Optional[bytes] = None, *, parse_payload: bool = True
) -> Optional[mesh_pb2.MeshPacket]:
    try:
        mp = mesh_pb2.MeshPacket()
        mp.ParseFromString(raw)

        if mp.HasField("encrypted") and not mp.HasField("decoded"):
            decoded = decrypt_packet(mp, key)
            if decoded is not None:
                mp.decoded.CopyFrom(decoded)
            # else: keep the encrypted packet as-is

        if parse_payload and mp.HasField("decoded"):
            portnum = mp.decoded.portnum
            handler = protocols.get(portnum) if portnum is not None else None
            if handler is not None and handler.protobufFactory is not None:
                pb = handler.protobufFactory()
                try:
                    pb.ParseFromString(mp.decoded.payload)
                    pb_str = str(pb).replace("\n", " ").replace("\r", " ").strip()
                    mp.decoded.payload = pb_str.encode("utf-8")
                except DecodeError:
                    pass

        return mp
    except DecodeError:
        return None


class UDPPacketStream:
    """
    Background listener that publishes:
      - 'mesh.rx.raw'(data)
      - 'mesh.rx.decode_error'(addr)
      - 'mesh.rx.packet'(packet, addr)  # every successfully parsed packet, including duplicates
      - 'mesh.rx.unique_packet'(packet, addr)
      - 'mesh.rx.duplicate'(packet, addr)
      - 'mesh.rx.decoded'(packet, portnum, addr)  # unique packets only
      - 'mesh.rx.port.<portnum>'(packet, addr)  # per-port topic for unique packets only
    """

    def __init__(
        self,
        mcast_grp: str,
        mcast_port: int,
        key: Optional[bytes] = None,
        recv_buf: int = 65535,
        parse_payload: bool = True,
        select_timeout: float = 0.2,
        dedupe_ttl_sec: float = 60.0,
        dedupe_max_entries: int = 4096,
    ) -> None:
        self.mcast_grp = mcast_grp
        self.mcast_port = mcast_port
        self.key = key
        self.recv_buf = recv_buf
        self.parse_payload = parse_payload
        self.select_timeout = select_timeout
        self.dedupe_ttl_sec = max(float(dedupe_ttl_sec), 0.0)
        self.dedupe_max_entries = max(int(dedupe_max_entries), 1)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock = None
        self._seen_packets: OrderedDict[tuple[int, int], float] = OrderedDict()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        conn.setup_multicast(self.mcast_grp, self.mcast_port)

        # Try to grab underlying socket and make it non-blocking
        self._sock = getattr(conn, "sock", None) or getattr(conn, "socket", None)
        if self._sock is not None:
            try:
                self._sock.setblocking(False)
            except Exception:
                try:
                    self._sock.settimeout(0.0)
                except Exception:
                    pass

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="UDPPacketStream", daemon=True)
        self._thread.start()

    def stop(self, join: bool = True) -> None:
        self._stop.set()
        if join and self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _packet_dedupe_key(self, packet: mesh_pb2.MeshPacket) -> tuple[int, int] | None:
        from_id = int(getattr(packet, "from", 0) or 0)
        packet_id = int(getattr(packet, "id", 0) or 0)
        if from_id <= 0 or packet_id <= 0:
            return None
        return (from_id, packet_id)

    def _prune_seen_packets(self, now: float) -> None:
        if self.dedupe_ttl_sec > 0:
            expiry_cutoff = now - self.dedupe_ttl_sec
            while self._seen_packets:
                _, seen_at = next(iter(self._seen_packets.items()))
                if seen_at > expiry_cutoff:
                    break
                self._seen_packets.popitem(last=False)

        while len(self._seen_packets) > self.dedupe_max_entries:
            self._seen_packets.popitem(last=False)

    def _is_duplicate_packet(
        self,
        packet: mesh_pb2.MeshPacket,
        *,
        now: float | None = None,
    ) -> bool:
        key = self._packet_dedupe_key(packet)
        if key is None:
            return False

        check_time = time.monotonic() if now is None else float(now)
        self._prune_seen_packets(check_time)

        seen_at = self._seen_packets.get(key)
        if seen_at is not None:
            if self.dedupe_ttl_sec == 0 or (check_time - seen_at) <= self.dedupe_ttl_sec:
                self._seen_packets.move_to_end(key)
                self._seen_packets[key] = check_time
                return True
            self._seen_packets.pop(key, None)

        self._seen_packets[key] = check_time
        self._prune_seen_packets(check_time)
        return False

    def _publish_unique_topics(self, packet: mesh_pb2.MeshPacket, addr) -> None:
        pub.sendMessage("mesh.rx.unique_packet", packet=packet, addr=addr)

        if not packet.HasField("decoded"):
            return

        portnum = packet.decoded.portnum
        pub.sendMessage("mesh.rx.decoded", packet=packet, portnum=portnum, addr=addr)
        pub.sendMessage(f"mesh.rx.port.{portnum}", packet=packet, addr=addr)
        if portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            pub.sendMessage("mesh.rx.text", packet=packet, addr=addr)
            return

        if portnum != portnums_pb2.PortNum.ROUTING_APP:
            return

        routing = parse_routing(packet)
        if routing is None:
            return

        pub.sendMessage("mesh.rx.routing", packet=packet, routing=routing, addr=addr)
        if is_ack(packet):
            pending = pending_acks.resolve(packet.decoded.request_id)
            pub.sendMessage("mesh.rx.ack", packet=packet, routing=routing, addr=addr, pending=pending)
        elif is_nak(packet):
            pending = pending_acks.resolve(packet.decoded.request_id)
            pub.sendMessage("mesh.rx.nak", packet=packet, routing=routing, addr=addr, pending=pending)

    def _handle_datagram(self, raw: bytes, addr) -> None:
        pub.sendMessage("mesh.rx.raw", data=raw, addr=addr)

        packet = _decode_and_optionally_parse(raw, self.key, parse_payload=self.parse_payload)
        if packet is None:
            pub.sendMessage("mesh.rx.decode_error", addr=addr)
            return
        if not getattr(packet, "rx_time", 0):
            packet.rx_time = int(time.time())
        if not getattr(packet, "transport_mechanism", 0):
            packet.transport_mechanism = mesh_pb2.MeshPacket.TransportMechanism.TRANSPORT_MULTICAST_UDP

        pub.sendMessage("mesh.rx.packet", packet=packet, addr=addr)
        if self._is_duplicate_packet(packet):
            pub.sendMessage("mesh.rx.duplicate", packet=packet, addr=addr)
            return

        self._publish_unique_topics(packet, addr)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._sock is not None:
                    r, _, _ = select.select([self._sock], [], [], self.select_timeout)
                    if not r:
                        continue
                    raw, _addr = self._sock.recvfrom(self.recv_buf)
                else:
                    raw, _addr = conn.recvfrom(self.recv_buf)

                self._handle_datagram(raw, _addr)
            except Exception as e:
                pub.sendMessage("mesh.rx.listener_error", error=e)
