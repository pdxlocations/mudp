import math
import time
import requests

from mudp import send_position, send_nodeinfo, conn, node


def setup():
    node.channel = "MediumFast"
    node.key = "1PG7OiApB1nwvP+rz05pAQ=="
    node.node_id = "!b155b155"
    node.long_name = "ISS"
    node.short_name = "🛰"
    MCAST_GRP = "224.0.0.69"
    MCAST_PORT = 4403
    conn.setup_multicast(MCAST_GRP, MCAST_PORT)


def get_iss_location():
    try:
        response = requests.get("https://api.wheretheiss.at/v1/satellites/25544")
        response.raise_for_status()
        data = response.json()
        return data["latitude"], data["longitude"], data["altitude"] * 1000, data["velocity"]
    except Exception as e:
        print(f"[ERROR] Failed to fetch ISS location: {e}")
        return None, None, None


def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360


def main():

    setup()
    send_nodeinfo()
    time.sleep(3)
    last_nodeinfo_time = time.time()
    last_lat, last_lon = None, None

    try:
        while True:
            lat, lon, alt, velocity = get_iss_location()
            if lat is not None and lon is not None:
                ground_track = None
                if last_lat is not None and last_lon is not None:
                    ground_track = int(calculate_bearing(last_lat, last_lon, lat, lon))

                print(
                    f"\n[ISS] Lat: {lat:.4f}, Lon: {lon:.4f}, Alt: {alt:.2f} m, Vel: {velocity:.2f} m/s"
                    + (f", Track: {ground_track:.1f}°" if ground_track is not None else "")
                )

                send_position(
                    latitude=lat,
                    longitude=lon,
                    altitude=int(alt),
                    precision_bits=32,
                    ground_speed=int(velocity),
                    ground_track=ground_track,
                )
                time.sleep(3)
                last_lat, last_lon = lat, lon
                if time.time() - last_nodeinfo_time > 7200:
                    send_nodeinfo()
                    last_nodeinfo_time = time.time()
            time.sleep(300)
    except KeyboardInterrupt:
        print("\nDisconnecting...")


if __name__ == "__main__":
    main()
