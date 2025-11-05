from dataclasses import dataclass


@dataclass
class Node:
    node_id: str = ""
    long_name: str = "unnamed"
    short_name: str = "??"
    hw_model: int = 255
    role: str = "CLIENT"
    macaddr: bytes = b""
    public_key: bytes = b""
    channel: str = ""
    key: str = ""
