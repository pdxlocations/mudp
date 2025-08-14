import time
from pubsub import pub
from google.protobuf import text_format

from meshtastic.protobuf import mesh_pb2, portnums_pb2
from mudp import UDPPacketStream

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "AQ=="

interface = UDPPacketStream(MCAST_GRP, MCAST_PORT, key=KEY)


def on_raw(data: bytes, addr=None):
    hex_data = " ".join(f"{b:02x}" for b in data)
    src = addr[0] if isinstance(addr, tuple) and len(addr) >= 1 else "unknown"
    print(f"\n[RECV] {len(data)} bytes from {src}")
    print("Hex:", hex_data)
    print(f"Bytes:", data)


def on_recieve(packet: mesh_pb2.MeshPacket, addr=None):
    print(f"\n[RECV] Packet received from {addr}")
    print("from:", getattr(packet, "from", None))
    print("to:", packet.to)
    print("channel:", packet.channel or None)

    if packet.HasField("decoded"):
        port_name = portnums_pb2.PortNum.Name(packet.decoded.portnum) if packet.decoded.portnum else "N/A"
        print("decoded {")
        print("  portnum:", port_name)
        try:
            print("  payload:", packet.decoded.payload.decode("utf-8", "ignore"))
        except Exception:
            print("  payload (raw bytes):", packet.decoded.payload)
        print("  bitfield:", packet.decoded.bitfield or None)
        print("}")
    else:
        print(f"encrypted: { {packet.encrypted} }")

    print("id:", packet.id or None)
    print("rx_time:", packet.rx_time or None)
    print("rx_snr:", packet.rx_snr or None)
    print("hop_limit:", packet.hop_limit or None)
    priority_name = mesh_pb2.MeshPacket.Priority.Name(packet.priority) if packet.priority else "N/A"
    print("priority:", priority_name or None)
    print("rx_rssi:", packet.rx_rssi or None)
    print("hop_start:", packet.hop_start or None)
    print("next_hop:", packet.next_hop or None)
    print("relay_node:", packet.relay_node or None)


def on_text_message(packet: mesh_pb2.MeshPacket, addr=None):
    msg = packet.decoded.payload.decode("utf-8", "ignore")
    print(f"\n[RECV] From: {getattr(packet, 'from', None)} Message: {msg}")


def on_node_info(packet: mesh_pb2.MeshPacket, addr=None):
    if not packet.HasField("decoded") or packet.decoded.portnum != portnums_pb2.PortNum.NODEINFO_APP:
        return
    user = mesh_pb2.User()
    payload = packet.decoded.payload
    try:
        user.ParseFromString(payload)
    except Exception:
        text_format.Parse(payload.decode("utf-8", "ignore"), user)

    print(f"\n[RECV] Node Information From:")
    print(f"   ID: {user.id or 'N/A'}")
    print(f"   Long Name: {user.long_name or 'N/A'}")
    print(f"   Short Name: {user.short_name or 'N/A'}")
    print(f"   MAC Address: {user.macaddr or 'N/A'}")
    hw = mesh_pb2.HardwareModel.Name(user.hw_model) if user.hw_model else "N/A"
    print(f"   Hardware Model: {hw}")


def on_decode_error(packet: mesh_pb2.MeshPacket, addr=None):
    sender = getattr(packet, "from_", getattr(packet, "from", None))
    print(f"\n[decode_error] from {sender}")


def main():
    # pub.subscribe(on_raw, "mesh.rx.raw")
    pub.subscribe(on_recieve, "mesh.rx.packet")
    pub.subscribe(on_text_message, "mesh.rx.port.1")
    pub.subscribe(on_node_info, "mesh.rx.port.4")
    # pub.subscribe(on_decode_error, "mesh.rx.decode_error")

    interface.start()

    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        interface.stop()


if __name__ == "__main__":
    main()
