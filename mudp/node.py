from dataclasses import dataclass


@dataclass
class Node:
    node_id: str = ""
    node_long_name: str = ""
    node_short_name: str = ""
    channel: str = ""
    key: str = ""
