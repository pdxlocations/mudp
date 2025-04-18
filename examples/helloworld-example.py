from mudp import (
    conn,
    node,
    send_nodeinfo,
    send_text_message,
    send_device_telemetry,
    send_position,
    send_environment_metrics,
    send_power_metrics,
)
from meshtastic import mesh_pb2
from google.protobuf.message import DecodeError
from mudp import decrypt_packet

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403


def setup_node():
    node.node_id = "!deadbeef"
    node.node_long_name = "UDP Test"
    node.node_short_name = "UDP"
    node.channel = "LongFast"
    node.key = "1PG7OiApB1nwvP+rz05pAQ=="
    conn.setup_multicast(MCAST_GRP, MCAST_PORT)


def demo_send_messages():
    send_nodeinfo()

    send_text_message("hello world")

    send_position(latitude=37.7749, longitude=-122.4194, altitude=10, precision_bits=3, ground_speed=5)

    send_device_telemetry(battery_level=50, voltage=3.7, channel_utilization=25, air_util_tx=15, uptime_seconds=123456)

    send_environment_metrics(
        temperature=23.072298,
        relative_humidity=17.5602016,
        barometric_pressure=995.36261,
        gas_resistance=229.093369,
        voltage=5.816,
        current=-29.3,
        iaq=66,
    )

    send_power_metrics(
        ch1_voltage=18.744,
        ch1_current=11.2,
        ch2_voltage=2.792,
        ch2_current=18.4,
        ch3_voltage=0,
        ch3_current=0,
    )


def listen_for_packets():
    print(f"Listening for UDP multicast packets on {MCAST_GRP}:{MCAST_PORT}...\n")
    while True:
        data, addr = conn.recvfrom(65535)

        try:
            mp = mesh_pb2.MeshPacket()
            mp.ParseFromString(data)

            if mp.HasField("encrypted") and not mp.HasField("decoded"):
                decoded_data = decrypt_packet(mp, node.key)
                if decoded_data is not None:
                    mp.decoded.CopyFrom(decoded_data)
                else:
                    print("*** [RX] Failed to decrypt message — decoded_data is None")

            print(f"[RECV from {addr}]\n{mp}")
        except DecodeError:
            print(f"[RECV from {addr}] Failed to decode protobuf")


def main():
    setup_node()
    demo_send_messages()
    listen_for_packets()


if __name__ == "__main__":
    main()
