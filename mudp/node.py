from dataclasses import dataclass


@dataclass
class Node:
    node_id: str = ""
    long_name: str = "unnnamed"
    short_name: str = "??"
    hw_model: int = 255
    public_key: bytes = b""
    channel: str = ""
    key: str = ""
