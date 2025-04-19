This library provides UDP-based broadcasting of Meshtastic-compatible packets.

# Installation

```bash
pip install mudp
```


# Functions (see examples for further information):

```python
from mudp import (
    conn,
    node,
    send_nodeinfo,
    send_text_message,
    send_device_telemetry,
    send_position,
    send_environment_metrics,
    send_power_metrics,
)

MCAST_GRP = "224.0.0.69"
MCAST_PORT = 4403

node.node_id = "!deadbeef"
node.long_name = "UDP Test"
node.short_name = "UDP"
node.channel = "LongFast"
node.key = "1PG7OiApB1nwvP+rz05pAQ=="
conn.setup_multicast(MCAST_GRP, MCAST_PORT)

send_nodeinfo()
send_device_telemetry(_keywords_)
send_position(latitude, longitude, _keywords_)
send_environment_metrics(_keywords_)
send_power_metrics(_keywords_)
send_health_metrics(_keywords_)
send_text_message("text", _keywords_)
```

Optional Arguments for all message types:

- to=INT
- hop_limit=INT
- hop_start=INT
- want_ack=BOOL
- want_response=BOOL

Example:
```python
send_text_message("Happy New Year" to=12345678, hop_limit=5)
```

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



## Install in development (editable) mode:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```