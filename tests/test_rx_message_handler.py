import unittest
from unittest import mock

from meshtastic.protobuf import mesh_pb2, portnums_pb2

from mudp.rx_message_handler import UDPPacketStream


def build_text_packet(*, from_id: int = 1234, packet_id: int = 5678) -> mesh_pb2.MeshPacket:
    packet = mesh_pb2.MeshPacket()
    packet.id = packet_id
    setattr(packet, "from", from_id)
    packet.to = 4321
    packet.decoded.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
    packet.decoded.payload = b"hello"
    return packet


def build_ack_packet(
    *,
    from_id: int = 1234,
    packet_id: int = 5678,
    request_id: int = 9999,
) -> mesh_pb2.MeshPacket:
    packet = mesh_pb2.MeshPacket()
    packet.id = packet_id
    setattr(packet, "from", from_id)
    packet.to = 4321
    packet.decoded.portnum = portnums_pb2.PortNum.ROUTING_APP
    packet.decoded.request_id = request_id

    routing = mesh_pb2.Routing()
    routing.error_reason = mesh_pb2.Routing.Error.NONE
    packet.decoded.payload = routing.SerializeToString()
    return packet


class UDPPacketStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = UDPPacketStream(
            "224.0.0.69",
            4403,
            parse_payload=False,
            dedupe_ttl_sec=10.0,
            dedupe_max_entries=32,
        )
        self.addr = ("127.0.0.1", 4403)

    def test_duplicate_text_packet_only_emits_semantic_topics_once(self) -> None:
        packet = build_text_packet()
        raw = packet.SerializeToString()

        with mock.patch("mudp.rx_message_handler.pub.sendMessage") as send_message:
            self.stream._handle_datagram(raw, self.addr)
            self.stream._handle_datagram(raw, self.addr)

        topics = [call.args[0] for call in send_message.call_args_list]
        self.assertEqual(topics.count("mesh.rx.raw"), 2)
        self.assertEqual(topics.count("mesh.rx.packet"), 2)
        self.assertEqual(topics.count("mesh.rx.unique_packet"), 1)
        self.assertEqual(topics.count("mesh.rx.decoded"), 1)
        self.assertEqual(topics.count("mesh.rx.text"), 1)
        self.assertEqual(topics.count(f"mesh.rx.port.{portnums_pb2.PortNum.TEXT_MESSAGE_APP}"), 1)
        self.assertEqual(topics.count("mesh.rx.duplicate"), 1)

    def test_duplicate_routing_ack_resolves_pending_once(self) -> None:
        packet = build_ack_packet()
        raw = packet.SerializeToString()

        with (
            mock.patch("mudp.rx_message_handler.pub.sendMessage") as send_message,
            mock.patch("mudp.rx_message_handler.pending_acks.resolve", return_value=object()) as resolve,
        ):
            self.stream._handle_datagram(raw, self.addr)
            self.stream._handle_datagram(raw, self.addr)

        topics = [call.args[0] for call in send_message.call_args_list]
        self.assertEqual(topics.count("mesh.rx.routing"), 1)
        self.assertEqual(topics.count("mesh.rx.ack"), 1)
        self.assertEqual(topics.count("mesh.rx.duplicate"), 1)
        resolve.assert_called_once_with(packet.decoded.request_id)

    def test_packets_without_stable_identity_are_not_deduped(self) -> None:
        packet = build_text_packet(from_id=0, packet_id=0)
        raw = packet.SerializeToString()

        with mock.patch("mudp.rx_message_handler.pub.sendMessage") as send_message:
            self.stream._handle_datagram(raw, self.addr)
            self.stream._handle_datagram(raw, self.addr)

        topics = [call.args[0] for call in send_message.call_args_list]
        self.assertEqual(topics.count("mesh.rx.unique_packet"), 2)
        self.assertEqual(topics.count("mesh.rx.duplicate"), 0)
        self.assertEqual(topics.count("mesh.rx.text"), 2)

    def test_dedupe_entries_expire_after_ttl(self) -> None:
        packet = build_text_packet()

        self.assertFalse(self.stream._is_duplicate_packet(packet, now=0.0))
        self.assertTrue(self.stream._is_duplicate_packet(packet, now=5.0))
        self.assertFalse(self.stream._is_duplicate_packet(packet, now=16.0))


if __name__ == "__main__":
    unittest.main()
