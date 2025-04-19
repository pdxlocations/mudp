from mudp import listen_for_packets

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403
KEY = "1PG7OiApB1nwvP+rz05pAQ=="


def start() -> None:

    listen_for_packets(MCAST_GRP, MCAST_PORT, KEY)


if __name__ == "__main__":
    start()
