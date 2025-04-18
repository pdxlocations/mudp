import socket


class Connection:
    def __init__(self):
        self.socket = None
        self.host = None
        self.port = None

    def setup_multicast(self, group: str, port: int):
        self.host = group
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass
        self.socket.bind(("", port))
        mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def recvfrom(self, bufsize: int = 4096):
        if not self.socket:
            raise RuntimeError("Socket is not initialized.")
        return self.socket.recvfrom(bufsize)

    def sendto(self, data: bytes, addr):
        if not self.socket:
            raise RuntimeError("Socket is not initialized.")
        self.socket.sendto(data, addr)
