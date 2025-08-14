import time
from pubsub import pub
from google.protobuf import text_format

from meshtastic.protobuf import mesh_pb2
from mudp import UDPPacketStream
from mudp.singleton import conn


MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "AQ=="


def on_any_packet(packet: mesh_pb2.MeshPacket):
    """Catch-all for any packet the UDPPacketStream publishes."""
    sender = getattr(packet, "from_", getattr(packet, "from", None))
    port = packet.decoded.portnum if packet.HasField("decoded") else None
    print(f"[any] id={packet.id} from={sender} to={packet.to} port={port}")


def on_raw(data: bytes):
    hex_data = " ".join(f"{b:02x}" for b in data)
    print(f"[raw] {len(data)} bytes")
    print("Hex:", hex_data)
    print(f"Bytes:", data)


def on_recieve(packet: mesh_pb2.MeshPacket):

    print("id:", packet.id)
    print("from:", getattr(packet, "from", None))
    print("to:", packet.to)

    if packet.HasField("decoded"):
        print("portnum:", packet.decoded.portnum)
        try:
            print("payload:", packet.decoded.payload.decode("utf-8", "ignore"))
        except Exception:
            print("payload (raw bytes):", packet.decoded.payload)
    print()


def on_text_message(packet: mesh_pb2.MeshPacket):
    print(f"{packet.decoded.payload} {getattr(packet, 'from', None)}")


def on_node_info(packet: mesh_pb2.MeshPacket):

    user = mesh_pb2.User()
    payload = packet.decoded.payload  # bytes

    try:
        text = payload.decode("utf-8", "ignore")
        text_format.Parse(text, user)
    except Exception as e:
        print(f"[node_info] failed to parse User payload: {e}")
        print("raw payload bytes:", payload)
        return

    print(f" Node Information From IP: {getattr(packet, '_src_addr', ['N/A'])[0]}")
    print(f"    ID: {user.id or 'N/A'}")
    print(f"    Long Name: {user.long_name or 'N/A'}")
    print(f"    Short Name: {user.short_name or 'N/A'}")
    print(f"    MAC Address: {user.macaddr or 'N/A'}")
    hw = mesh_pb2.HardwareModel.Name(user.hw_model) if user.hw_model else "N/A"
    print(f"    Hardware Model: {hw}")


def on_decode_error(packet: mesh_pb2.MeshPacket):
    sender = getattr(packet, "from_", getattr(packet, "from", None))
    print(f"[decode_error] from {sender}")


def main():

    # pub.subscribe(on_raw, "mesh.rx.raw")
    pub.subscribe(on_recieve, "mesh.rx.packet")
    # pub.subscribe(on_decode_error, "mesh.rx.decode_error")
    # pub.subscribe(on_text_message, "mesh.rx.port.1")
    # pub.subscribe(on_node_info, "mesh.rx.port.4")

    interface = UDPPacketStream(MCAST_GRP, MCAST_PORT, key=KEY)
    interface.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        interface.stop()


if __name__ == "__main__":
    main()
