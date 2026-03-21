import os
import socket
import sys


class Connection:
    def __init__(self):
        self.socket = None
        self.sock = None
        self.host = None
        self.port = None

    def setup_multicast(self, group: str, port: int, bind_mode: str | None = None):
        self.host = group
        self.port = port

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        env_bind_mode = os.getenv("MUDP_BIND_MODE") or os.getenv("FIREFLY_MUDP_BIND_MODE")
        bind_mode = (bind_mode or env_bind_mode or "auto").strip().lower()
        if bind_mode == "group":
            bind_targets = [(group, port)]
        elif bind_mode == "any":
            bind_targets = [("", port)]
        elif sys.platform.startswith("linux"):
            bind_targets = [(group, port), ("", port)]
        else:
            bind_targets = [("", port), (group, port)]

        last_error = None
        for bind_host, bind_port in bind_targets:
            try:
                sock.bind((bind_host, bind_port))
                break
            except OSError as exc:
                last_error = exc
        else:
            sock.close()
            raise last_error

        mreq = socket.inet_aton(group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.socket = sock
        self.sock = sock

    def recvfrom(self, bufsize: int = 4096):
        if not self.socket:
            raise RuntimeError("Socket is not initialized.")
        return self.socket.recvfrom(bufsize)

    def sendto(self, data: bytes, addr):
        if not self.socket:
            raise RuntimeError("Socket is not initialized.")
        self.socket.sendto(data, addr)
