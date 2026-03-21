This library provides UDP-based broadcasting of Meshtastic-compatible packets.

# Installation

```bash
pip install mudp
```


# Command Line

To view all Meshtastic udp activity on your LAN:
```bash
mudp
```

`mudp` accepts the Meshtastic 1-byte PSK aliases `AQ==`, `Ag==`, `Aw==`, `BA==`, `BQ==`, `Bg==`, and `Bw==` anywhere a channel key is used and normalizes them internally.

If multicast binding needs tuning, set `MUDP_BIND_MODE` to `auto`, `group`, or `any`.
`auto` prefers binding to the multicast group first on Linux, then falls back to `0.0.0.0`.

# PubSub RX Topics

When using this library as a listener, it can publish received packets to the Python `pubsub` system. The following topics are available:

- **mesh.rx.raw** – publishes `(data, addr)` with the raw UDP packet bytes and source address tuple.
- **mesh.rx.decode_error** – publishes `(addr)` when a packet fails to decode.
- **mesh.rx.packet** – publishes `(packet, addr)` for all successfully parsed `MeshPacket` objects, including duplicates.
- **mesh.rx.unique_packet** – publishes `(packet, addr)` only for the first copy of a packet seen by the listener.
- **mesh.rx.duplicate** – publishes `(packet, addr)` when the listener sees the same `(from, id)` again.
- **mesh.rx.decoded** – publishes `(packet, portnum, addr)` when the decoded portion is available for a unique packet.
- **mesh.rx.port.&lt;portnum&gt;** – publishes `(packet, addr)` for filtering unique packets by port number.
- **mesh.rx.text** – publishes `(packet, addr)` for unique decoded `TEXT_MESSAGE_APP` packets.
- **mesh.rx.routing** – publishes `(packet, routing, addr)` for unique decoded `ROUTING_APP` packets.
- **mesh.rx.ack** – publishes `(packet, routing, addr, pending)` for unique routing ACKs and clears any matching pending outbound ACK state.
- **mesh.rx.nak** – publishes `(packet, routing, addr, pending)` for unique routing NAKs and clears any matching pending outbound ACK state.

Use **mesh.rx.packet** when you need every wire observation.
Use **mesh.rx.unique_packet** and the decoded/per-port/text/routing topics for application logic that should run once per logical message.

`UDPPacketStream` also accepts `dedupe_ttl_sec` and `dedupe_max_entries` to tune how long `(from, id)` observations stay in the duplicate-suppression cache and how large that cache can grow.

# Reliability Topics

When sending direct packets with `want_ack=True`, `mudp` tracks pending ACK state and retransmits
the original serialized packet if no ACK or NAK is received.

- **mesh.tx.retry** – publishes `(pending)` when a tracked outbound packet is retransmitted.
- **mesh.tx.retry_error** – publishes `(pending, error)` if a retransmit send attempt fails locally.
- **mesh.tx.max_retransmit** – publishes `(pending, error_reason)` when retry attempts are exhausted.

Current behavior:

- direct `want_ack` packets are retried
- broadcast packets are not retried
- ACK and NAK handling uses `ROUTING_APP` packets
- duplicate classification happens at the listener level using a TTL-backed `(from, id)` cache

# Send Functions (see examples for further information):

```python
from mudp import (
    conn,
    node,
    send_nodeinfo,
    send_reply,
    send_text_message,
    send_device_telemetry,
    send_position,
    send_environment_metrics,
    send_power_metrics,
    send_health_metrics,
    send_waypoint,
    send_data,
)

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403

node.node_id = "!deadbeef"
node.long_name = "UDP Test"
node.short_name = "UDP"
node.channel = "LongFast"
node.key = "1PG7OiApB1nwvP+rz05pAQ=="
conn.setup_multicast(MCAST_GRP, MCAST_PORT)

send_text_message("text", keys=values...)
send_reply("text", packet.id, keys=values...)
send_reply("👍", packet.id, emoji=True, keys=values...)
send_nodeinfo(keys=values...)
send_device_telemetry(keys=values...)
send_position(latitude, longitude, keys=values...)
send_environment_metrics(keys=values...)
send_power_metrics(keys=values...)
send_health_metrics(keys=values...)
send_waypoint(latitude, longitude, keys=values...)
send_data(destination_id, payload, portnum=256, want_ack=False)

Optional Arguments for all message types:

- to=INT
- hop_limit=INT
- hop_start=INT
- want_ack=BOOL
- want_response=BOOL

Example:
```python
send_text_message("Happy New Year", to=12345678, hop_limit=5)
send_reply("👍", reply_id=packet.id, emoji=True)
send_reply("message received", reply_id=packet.id)
send_data("!deadbeef", b"raw bytes here", portnum=256, want_ack=True)
```

Use `emoji=True` when the reply payload is an emoji reaction. Plain-text replies only need `reply_id`.

Supported keyword arguments for nodeinfo:

- node_id
- long_name
- short_name
- hw_model
- is_licensed
- role
- public_key

Supported keyword arguments for device metrics:

 - battery_level
 - voltage
 - channel_utilization
 - air_util_tx
 - uptime_seconds

Supported keyword arguments for position metrics:

- latitude (required)
- longitude (required)
- latitude_i
- longitude_i
- altitude
- precision_bits
- HDOP
- PDOP
- VDOP
- altitude_geoidal_separation
- altitude_hae
- altitude_source
- fix_quality
- fix_type
- gps_accuracy
- ground_speed
- ground_track
- next_update
- sats_in_view
- sensor_id
- seq_number
- timestamp
- timestamp_millis_adjust

Supported keyword arguments for environment metrics:

- temperature
- relative_humidity
- barometric_pressure
- gas_resistance
- voltage
- current
- iaq
- distance
- ir_lux
- lux
- radiation
- rainfall_1h
- rainfall_24h
- soil_moisture
- soil_temperature
- uv_lux
- weight
- white_lux
- wind_direction
- wind_gust
- wind_lull
- wind_speed

Supported keyword arguments for power metrics:

 - ch1_voltage
 - ch1_current
 - ch2_voltage
 - ch2_current
 - ch3_voltage
 - ch3_current

Supported keyword arguments for health metrics:
 
 - heart_bpm
 - spO2
 - temperature

Supported keyword arguments for waypoints:

- id
- latitude
- longitude
- expire
- locked_to
- name
- description
- icon


## Install in development (editable) mode:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
