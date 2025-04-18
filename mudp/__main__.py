from meshtastic import BROADCAST_NUM

from meshtastic.protobuf import mesh_pb2
from google.protobuf.message import DecodeError


def start() -> None:

    ...
    # print(f"Listening for UDP multicast packets on {MCAST_GRP}:{MCAST_PORT}...\n")
    # while True:
    #     data, addr = conn.recvfrom(65535)

    #     try:
    #         mp = mesh_pb2.MeshPacket()
    #         mp.ParseFromString(data)

    #         if mp.HasField("encrypted") and not mp.HasField("decoded"):
    #             decoded_data = decrypt_packet(mp, KEY)
    #             if decoded_data is not None:
    #                 mp.decoded.CopyFrom(decoded_data)
    #             else:
    #                 print("*** [RX] Failed to decrypt message — decoded_data is None")

    #         print(f"[RECV from {addr}]\n{mp}")
    #     except DecodeError:
    #         print(f"[RECV from {addr}] Failed to decode protobuf")


if __name__ == "__main__":
    start()
