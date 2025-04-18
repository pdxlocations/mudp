import random

from typing import Callable
from meshtastic import portnums_pb2, mesh_pb2, telemetry_pb2, BROADCAST_NUM
from mudp.encryption import generate_hash, encrypt_packet
from mudp.singleton import conn, node


message_id = random.getrandbits(32)


def create_payload(data, portnum: int, bitfield: int = 1, **kwargs) -> bytes:
    """Generalized function to create a payload."""
    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnum
    encoded_message.payload = data.SerializeToString() if hasattr(data, "SerializeToString") else data
    encoded_message.want_response = kwargs.get("want_response", False)
    encoded_message.bitfield = bitfield
    return generate_mesh_packet(encoded_message, **kwargs)


def generate_mesh_packet(encoded_message: mesh_pb2.Data, **kwargs) -> bytes:
    """Generate the final mesh packet."""

    from_id = int(node.node_id.replace("!", ""), 16)
    destination = BROADCAST_NUM

    reserved_ids = [1, 2, 3, 4, 4294967295]
    if from_id in reserved_ids:
        raise ValueError(f"Node ID '{from_id}' is reserved and cannot be used. Please choose a different ID.")

    global message_id
    message_id = get_message_id(message_id)

    mesh_packet = mesh_pb2.MeshPacket()
    mesh_packet.id = message_id
    setattr(mesh_packet, "from", from_id)
    mesh_packet.to = int(destination)
    mesh_packet.want_ack = kwargs.get("want_ack", False)
    mesh_packet.channel = generate_hash(node.channel, node.key)
    mesh_packet.hop_limit = kwargs.get("hop_limit", 3)
    mesh_packet.hop_start = kwargs.get("hop_start", 3)

    if node.key == "":
        mesh_packet.decoded.CopyFrom(encoded_message)
    else:
        mesh_packet.encrypted = encrypt_packet(node.channel, node.key, mesh_packet, encoded_message)

    return mesh_packet.SerializeToString()


def get_portnum_name(portnum: int) -> str:
    for name, number in portnums_pb2.PortNum.items():
        if number == portnum:
            return name
    return f"UNKNOWN_PORTNUM ({portnum})"


def publish_message(payload_function: Callable, portnum: int, **kwargs) -> None:
    """Send a message of any type, with logging."""

    try:

        payload = payload_function(portnum=portnum, **kwargs)
        print(f"\n[TX] Portnum = {get_portnum_name(portnum)} ({portnum})")

        print(f"     To: {BROADCAST_NUM}")
        for k, v in kwargs.items():
            if k not in ("use_config", "to", "channel", "key") and v is not None:
                print(f"     {k}: {v}")

        conn.sendto(payload, (conn.host, conn.port))

        print(f"[SENT] {payload}")

    except Exception as e:
        print(f"Error while sending message: {e}")


def get_message_id(rolling_message_id: int, max_message_id: int = 4294967295) -> int:
    """Increment the message ID with sequential wrapping and add a random upper bit component to prevent predictability."""
    rolling_message_id = (rolling_message_id + 1) % (max_message_id & 0x3FF + 1)
    random_bits = random.randint(0, (1 << 22) - 1) << 10
    message_id = rolling_message_id | random_bits
    return message_id


def send_nodeinfo(**kwargs) -> None:
    """Send node information including short/long names and hardware model."""

    if "hw_model" not in kwargs:
        kwargs["hw_model"] = 255

    def create_nodeinfo_payload(portnum: int, **kwargs) -> bytes:
        """Constructs a nodeinfo payload message."""
        nodeinfo = mesh_pb2.User()

        for k, v in kwargs.items():
            if v is not None and k in mesh_pb2.User.DESCRIPTOR.fields_by_name:
                setattr(nodeinfo, k, v)
        return create_payload(nodeinfo, portnum, **kwargs)

    publish_message(
        create_nodeinfo_payload,
        portnum=portnums_pb2.NODEINFO_APP,
        node_id=node.node_id,
        long_name=node.node_long_name,
        short_name=node.node_short_name,
        **kwargs,
    )


def send_text_message(message: str = None, **kwargs) -> None:
    """Send a text message to the specified destination."""

    def create_text_payload(portnum: int, message: str = None, **kwargs):
        data = message.encode("utf-8")
        return create_payload(data, portnum, **kwargs)

    publish_message(create_text_payload, portnums_pb2.TEXT_MESSAGE_APP, message=message, **kwargs)
