import time

from pubsub import pub

from mudp import UDPPacketStream, conn, node, send_reply

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "AQ=="

interface = UDPPacketStream(MCAST_GRP, MCAST_PORT, key=KEY)


class ReplyBot:
    def __init__(self) -> None:
        self.reply_with_emoji = True

    def on_text_message(self, packet, addr=None) -> None:
        if not packet.HasField("decoded"):
            return

        my_node_id = int(node.node_id.replace("!", ""), 16)
        sender_id = getattr(packet, "from", None)
        if sender_id == my_node_id:
            return

        # Ignore replies so the bot does not start a reply chain.
        if packet.decoded.reply_id:
            print(f"[SKIP] Packet {packet.id} is already a reply to {packet.decoded.reply_id}")
            return

        message = packet.decoded.payload.decode("utf-8", "ignore")
        print(f"\n[RECV] From: {sender_id} Message: {message}")

        if self.reply_with_emoji:
            reply_message = "👍"
            emoji = True
        else:
            reply_message = "message received"
            emoji = False

        send_reply(
            reply_message,
            reply_id=packet.id,
            emoji=emoji,
            # Preserve the original routing envelope on the reply.
            to=packet.to,
            hop_limit=packet.hop_limit or 3,
            hop_start=packet.hop_start or packet.hop_limit or 3,
        )
        print(f"[REPLY] Sent {'emoji' if emoji else 'text'} reply to message {packet.id}")

        self.reply_with_emoji = not self.reply_with_emoji


def setup_node() -> None:
    node.node_id = "!deadbeef"
    node.long_name = "Reply Bot"
    node.short_name = "RPLY"
    node.channel = "MeshOregon"
    node.key = "AQ=="
    conn.setup_multicast(MCAST_GRP, MCAST_PORT)


def main() -> None:
    setup_node()
    bot = ReplyBot()

    # `mesh.rx.text` only fires once per logical text packet.
    pub.subscribe(bot.on_text_message, "mesh.rx.text")
    interface.start()

    print("Reply bot listening for text messages.")
    print("Replies alternate between an emoji and plain text.")

    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        interface.stop()


if __name__ == "__main__":
    main()
