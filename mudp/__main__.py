import time
from pubsub import pub
from mudp import UDPPacketStream
from meshtastic.protobuf import mesh_pb2

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "1PG7OiApB1nwvP+rz05pAQ=="


def on_recieve(packet: mesh_pb2.MeshPacket, addr=None):
    print(f"\n[RECV] Packet received from {addr}")
    print(packet)


def start() -> None:
    interface = UDPPacketStream(MCAST_GRP, MCAST_PORT, key=KEY)
    pub.subscribe(on_recieve, "mesh.rx.packet")
    interface.start()
    print(f"Listening for UDP multicast packets on {MCAST_GRP}:{MCAST_PORT}...")
    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        interface.stop()


if __name__ == "__main__":
    start()
