from dataclasses import dataclass


@dataclass
class Node:
    node_id: str = ""
    long_name: str = ""
    short_name: str = ""
    public_key: bytes = b""
    channel: str = ""
    key: str = ""
