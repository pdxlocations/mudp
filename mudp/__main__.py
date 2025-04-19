from meshtastic.protobuf import mesh_pb2
from google.protobuf.message import DecodeError
from mudp import decrypt_packet, conn
from meshtastic import protocols

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "1PG7OiApB1nwvP+rz05pAQ=="


def start() -> None:

    conn.setup_multicast(MCAST_GRP, MCAST_PORT)

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

            if mp.HasField("encrypted") and not mp.HasField("decoded"):
                decrypt_packet(mp)

            portNumInt = mp.decoded.portnum if mp.HasField("decoded") else None
            handler = protocols.get(portNumInt) if portNumInt else None

            pb = None
            if handler is not None and handler.protobufFactory is not None:
                pb = handler.protobufFactory()
                pb.ParseFromString(mp.decoded.payload)

            if pb:
                pb_str = str(pb).replace("\n", " ").replace("\r", " ").strip()
                mp.decoded.payload = pb_str.encode("utf-8")

            print(f"[RECV from {addr}]\n{mp}")
        except DecodeError:
            print(f"[RECV from {addr}] Failed to decode protobuf")


if __name__ == "__main__":
    start()
