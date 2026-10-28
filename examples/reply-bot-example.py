"""DM-only Meshtastic 2.8 reply bot using vnode's identity, signing, and PKI.

Install the optional runtime: pip install 'vnode>=0.1.11'
Identity and network settings live in node.json; no node ID is assigned here.
"""

from pathlib import Path

VNODE_FILE = Path("node.json")


class ReplyBot:
    def __init__(self, node):
        self.node = node
        self.reply_with_emoji = True

    def on_receive(self, packet, interface=None):
        if interface is not self.node:
            return
        raw = packet.get("raw") if isinstance(packet, dict) else None
        if raw is None or not self.node.is_direct_message_for_me(raw):
            return
        if not self.node.is_text_message(raw) or raw.decoded.reply_id:
            return
        message = "👍" if self.reply_with_emoji else "message received"
        # reply_to_packet targets the original sender and selects PKI automatically.
        self.node.reply_to_packet(raw, message, emoji=self.reply_with_emoji)
        self.reply_with_emoji = not self.reply_with_emoji


def main():
    try:
        from vnode import VirtualNode
    except ImportError as exc:
        raise SystemExit(
            "Install this example's runtime: pip install 'vnode>=0.1.11'"
        ) from exc
    node = VirtualNode(VNODE_FILE)
    bot = ReplyBot(node)
    node.receive(bot.on_receive)
    try:
        node.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        node.unreceive(bot.on_receive)
        node.close()


if __name__ == "__main__":
    main()
