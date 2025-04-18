from meshtastic import BROADCAST_NUM

from meshtastic.protobuf import mesh_pb2
from google.protobuf.message import DecodeError

from encryption import decrypt_packet
from tx_message_handler import send_nodeinfo

from connection import Connection

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "1PG7OiApB1nwvP+rz05pAQ=="

node_id = "!deadbeef"
long_name = "UDP Test"
short_name = "UDP"

conn = Connection()
conn.setup_multicast("224.0.0.69", 4403)


def start() -> None:
    send_nodeinfo(node_id, long_name, short_name, conn=conn.socket)

    print(f"Listening for UDP multicast packets on {MCAST_GRP}:{MCAST_PORT}...\n")
    while True:
        data, addr = conn.recvfrom(65535)

        try:
            mp = mesh_pb2.MeshPacket()
            mp.ParseFromString(data)

            if mp.HasField("encrypted") and not mp.HasField("decoded"):
                decoded_data = decrypt_packet(mp, KEY)
                if decoded_data is not None:
                    mp.decoded.CopyFrom(decoded_data)
                else:
                    print("*** [RX] Failed to decrypt message — decoded_data is None")

            print(f"[RECV from {addr}]\n{mp}")
        except DecodeError:
            print(f"[RECV from {addr}] Failed to decode protobuf")


if __name__ == "__main__":
    start()
