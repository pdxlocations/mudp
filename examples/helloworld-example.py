import time
from mudp import (
    conn,
    node,
    listen_for_packets,
    send_nodeinfo,
    send_text_message,
    send_device_telemetry,
    send_position,
    send_environment_metrics,
    send_power_metrics,
)

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403


def setup_node():
    node.node_id = "!deadbeef"
    node.long_name = "UDP Test"
    node.short_name = "UDP"
    node.channel = "LongFast"
    node.key = "AQ=="
    conn.setup_multicast(MCAST_GRP, MCAST_PORT)


def demo_send_messages():

    send_nodeinfo()
    time.sleep(3)

    send_text_message("hello world")
    time.sleep(3)

    send_position(latitude=37.7749, longitude=-122.4194, altitude=10, precision_bits=3, ground_speed=5)
    time.sleep(3)

    send_device_telemetry(battery_level=50, voltage=3.7, channel_utilization=25, air_util_tx=15, uptime_seconds=123456)
    time.sleep(3)

    send_environment_metrics(
        temperature=23.072298,
        relative_humidity=17.5602016,
        barometric_pressure=995.36261,
        gas_resistance=229.093369,
        voltage=5.816,
        current=-29.3,
        iaq=66,
    )
    time.sleep(3)

    send_power_metrics(
        ch1_voltage=18.744,
        ch1_current=11.2,
        ch2_voltage=2.792,
        ch2_current=18.4,
        ch3_voltage=0,
        ch3_current=0,
    )
    time.sleep(3)


def main():
    setup_node()
    demo_send_messages()
    listen_for_packets(MCAST_GRP, MCAST_PORT, node.key)


if __name__ == "__main__":
    main()
