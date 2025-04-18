from dataclasses import dataclass


@dataclass
class Node:
    node_id: str = ""
    long_name: str = ""
    short_name: str = ""
    channel: str = ""
    key: str = ""
