import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from meshtastic import mesh_pb2
from mudp.singleton import node, conn
from mudp.tx_message_handler import send_nodeinfo
from mudp.encryption import decrypt_packet


class NodeInfoTests(unittest.TestCase):
    def test_nodeinfo_includes_fixed_mac_and_preserves_explicit_mac(self):
        for mac in [None, bytes.fromhex("010203040506")]:
            with (
                self.subTest(mac=mac),
                patch.multiple(
                    node,
                    node_id="!12345678",
                    channel="LongFast",
                    key="AQ==",
                    macaddr=b"",
                ),
                patch.object(conn, "sendto") as send,
            ):
                send_nodeinfo(**({} if mac is None else {"macaddr": mac}))
                self.assertEqual(send.call_count, 1)
                packet = mesh_pb2.MeshPacket.FromString(send.call_args.args[0])
                data = decrypt_packet(packet, "AQ==")
                user = mesh_pb2.User.FromString(data.payload)
                self.assertEqual(user.macaddr, bytes(6) if mac is None else mac)


def load_bot():
    path = Path(__file__).resolve().parents[1] / "examples/reply-bot-example.py"
    spec = importlib.util.spec_from_file_location("reply_bot_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplyBotTests(unittest.TestCase):
    def test_direct_message_delegates_reply_to_sender_using_pki_runtime(self):
        module = load_bot()
        runtime = Mock()
        runtime.is_direct_message_for_me.side_effect = (
            lambda p: p.to == 456 and getattr(p, "from") != 456
        )
        runtime.is_text_message.side_effect = lambda p: p.decoded.portnum == 1
        packet = mesh_pb2.MeshPacket(id=42, to=456)
        setattr(packet, "from", 123)
        packet.decoded.portnum = 1
        packet.decoded.payload = b"hello"
        bot = module.ReplyBot(runtime)
        bot.on_receive({"raw": packet}, interface=runtime)
        runtime.reply_to_packet.assert_called_once_with(packet, "👍", emoji=True)
        self.assertEqual(
            getattr(runtime.reply_to_packet.call_args.args[0], "from"), 123
        )
        runtime.reply_to_packet.reset_mock()
        packet.to = 0xFFFFFFFF
        bot.on_receive({"raw": packet}, interface=runtime)
        packet.to = 456
        packet.decoded.reply_id = 9
        bot.on_receive({"raw": packet}, interface=runtime)
        packet.decoded.reply_id = 0
        bot.on_receive({"raw": packet}, interface=object())
        runtime.reply_to_packet.assert_not_called()
