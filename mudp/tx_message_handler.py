import random
import time
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
    destination = kwargs.get("to", BROADCAST_NUM)

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
    hop_limit = kwargs.get("hop_limit", 3)
    hop_start = kwargs.get("hop_start", 3)
    if hop_limit > hop_start:
        hop_start = hop_limit
    mesh_packet.hop_limit = hop_limit
    mesh_packet.hop_start = hop_start

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

        print(f"     To: {kwargs.get('to', 'BROADCAST_NUM')}")
        for k, v in kwargs.items():
            if k not in ("use_config", "to", "channel", "key") and v is not None:
                print(f"     {k}: {v}")

        conn.sendto(payload, (conn.host, conn.port))

        print(f"\n[SENT] {payload}")

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

    if "node_id" not in kwargs:
        kwargs["node_id"] = node.node_id
    if "long_name" not in kwargs:
        kwargs["long_name"] = node.long_name
    if "short_name" not in kwargs:
        kwargs["short_name"] = node.short_name
    if "hw_model" not in kwargs:
        kwargs["hw_model"] = 255

    def create_nodeinfo_payload(portnum: int, **fields) -> bytes:
        nodeinfo = mesh_pb2.User(
            hw_model=fields.pop("hw_model", 255),
            id=fields.pop("node_id", node.node_id),
            long_name=fields.pop("long_name", node.long_name),
            short_name=fields.pop("short_name", node.short_name),
        )
        for k, v in fields.items():
            if v is not None and k in mesh_pb2.User.DESCRIPTOR.fields_by_name:
                setattr(nodeinfo, k, v)
        return create_payload(nodeinfo, portnum, **kwargs)

    publish_message(create_nodeinfo_payload, portnum=portnums_pb2.NODEINFO_APP, **kwargs)


def send_text_message(message: str = None, **kwargs) -> None:
    """Send a text message to the specified destination."""

    if "location_source" not in kwargs:
        kwargs["location_source"] = "LOC_MANUAL"

    def create_text_payload(portnum: int, message: str = None, **kwargs):
        data = message.encode("utf-8")
        return create_payload(data, portnum, **kwargs)

    publish_message(create_text_payload, portnums_pb2.TEXT_MESSAGE_APP, message=message, **kwargs)


def send_position(latitude: float = None, longitude: float = None, **kwargs) -> None:
    """Send current position with optional additional fields (e.g., ground_speed, fix_type, etc)."""

    def create_position_payload(portnum: int, **fields):
        position_fields = {
            "latitude_i": int(latitude * 1e7) if latitude is not None else None,
            "longitude_i": int(longitude * 1e7) if longitude is not None else None,
            "time": int(time.time()),
        }

        # Filter out None values and remove keys we've already handled
        reserved_keys = {"latitude", "longitude"}
        data = {k: v for k, v in fields.items() if v is not None and k not in reserved_keys}
        position_fields.update(data)

        return create_payload(mesh_pb2.Position(**position_fields), portnum)

    publish_message(
        create_position_payload, portnums_pb2.POSITION_APP, latitude=latitude, longitude=longitude, **kwargs
    )


def send_device_telemetry(**kwargs) -> None:
    """Send telemetry packet including battery, voltage, channel usage, and uptime."""

    def create_telemetry_payload(portnum: int, **_):
        metrics_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        metrics = telemetry_pb2.DeviceMetrics(**metrics_kwargs)
        data = telemetry_pb2.Telemetry(time=int(time.time()), device_metrics=metrics)
        return create_payload(data, portnum)

    publish_message(create_telemetry_payload, portnums_pb2.TELEMETRY_APP, **kwargs)


def send_power_metrics(**kwargs) -> None:
    """Send power metrics including voltage and current for three channels."""

    def create_power_metrics_payload(portnum: int, **_):
        metrics_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        metrics = telemetry_pb2.PowerMetrics(**metrics_kwargs)
        data = telemetry_pb2.Telemetry(time=int(time.time()), power_metrics=metrics)
        return create_payload(data, portnum)

    publish_message(create_power_metrics_payload, portnums_pb2.TELEMETRY_APP, **kwargs)


def send_environment_metrics(**kwargs) -> None:
    """Send environment metrics including temperature, humidity, pressure, and gas resistance."""

    def create_environment_metrics_payload(portnum: int, **_):
        # Filter out None values from kwargs
        metrics_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        metrics = telemetry_pb2.EnvironmentMetrics(**metrics_kwargs)
        data = telemetry_pb2.Telemetry(time=int(time.time()), environment_metrics=metrics)
        return create_payload(data, portnum)

    publish_message(create_environment_metrics_payload, portnums_pb2.TELEMETRY_APP, **kwargs)


def send_health_metrics(**kwargs) -> None:
    """Send health metrics including heart rate, SpO2, and body temperature."""

    def create_health_metrics_payload(portnum: int, **_):
        metrics_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        metrics = telemetry_pb2.HealthMetrics(**metrics_kwargs)
        data = telemetry_pb2.Telemetry(time=int(time.time()), health_metrics=metrics)
        return create_payload(data, portnum)

    publish_message(create_health_metrics_payload, portnums_pb2.TELEMETRY_APP, **kwargs)
