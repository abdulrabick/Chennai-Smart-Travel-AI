import json
import math
from pathlib import Path

import pandas as pd


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

GEOJSON_FILE = BASE_DIR / "data" / "processed" / "chennai_railway_tracks.geojson"

STATION_FILE = BASE_DIR / "data" / "processed" / "location_coordinates.csv"


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

RAILWAY_TYPE = "rail"

# Search for track points within this distance of a station
STATION_SEARCH_RADIUS = 300

# Report track endpoints that are close to each other
MAX_ENDPOINT_GAP = 100


# --------------------------------------------------
# DISTANCE CALCULATION
# --------------------------------------------------

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate approximate distance in metres."""

    earth_radius = 6371000

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return earth_radius * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


# --------------------------------------------------
# LOAD FILES
# --------------------------------------------------

def load_data():

    print("\nLOADING RAILWAY DATA...")

    if not GEOJSON_FILE.exists():
        raise FileNotFoundError(
            f"Railway GeoJSON not found: {GEOJSON_FILE}"
        )

    if not STATION_FILE.exists():
        raise FileNotFoundError(
            f"Station coordinate file not found: {STATION_FILE}"
        )

    with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    stations = pd.read_csv(STATION_FILE)

    print("GeoJSON loaded successfully.")
    print("Station coordinates loaded successfully.")

    return geojson, stations


# --------------------------------------------------
# EXTRACT RAILWAY FEATURES
# --------------------------------------------------

def extract_railway_features(geojson):

    railway_features = []

    for feature_id, feature in enumerate(
        geojson.get("features", [])
    ):

        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        if not geometry:
            continue

        railway_type = properties.get("railway")

        if railway_type != RAILWAY_TYPE:
            continue

        if geometry.get("type") != "LineString":
            continue

        coordinates = geometry.get("coordinates", [])

        if len(coordinates) < 2:
            continue

        railway_features.append({
            "id": feature_id,
            "name": properties.get("name", "Unnamed track"),
            "coordinates": coordinates
        })

    return railway_features


# --------------------------------------------------
# FIND TRACK POINTS NEAR STATIONS
# --------------------------------------------------

def inspect_station_matches(railway_features, stations):

    print("\n" + "=" * 60)
    print("STATION TRACK MATCHING")
    print("=" * 60)

    for _, station in stations.iterrows():

        station_name = station["location"]
        station_lat = float(station["latitude"])
        station_lon = float(station["longitude"])

        matches = []

        for feature in railway_features:

            for point in feature["coordinates"]:

                lon, lat = point[0], point[1]

                distance = calculate_distance(
                    station_lat,
                    station_lon,
                    lat,
                    lon
                )

                if distance <= STATION_SEARCH_RADIUS:

                    matches.append({
                        "distance": distance,
                        "feature_id": feature["id"],
                        "name": feature["name"],
                        "latitude": lat,
                        "longitude": lon
                    })

        matches.sort(key=lambda item: item["distance"])

        print(f"\nStation: {station_name}")

        if not matches:
            print("  No railway points found nearby.")
            continue

        for match in matches[:5]:

            print(
                f"  Feature {match['feature_id']} | "
                f"{match['name']} | "
                f"{match['distance']:.1f} metres"
            )


# --------------------------------------------------
# INSPECT RAILWAY FEATURE ENDPOINTS
# --------------------------------------------------

def collect_endpoints(railway_features):

    endpoints = []

    for feature in railway_features:

        coordinates = feature["coordinates"]

        for position, point in [
            ("START", coordinates[0]),
            ("END", coordinates[-1])
        ]:

            endpoints.append({
                "feature_id": feature["id"],
                "name": feature["name"],
                "position": position,
                "longitude": point[0],
                "latitude": point[1]
            })

    return endpoints


def inspect_endpoint_gaps(railway_features):

    print("\n" + "=" * 60)
    print("NEARBY RAILWAY ENDPOINTS")
    print("=" * 60)

    endpoints = collect_endpoints(railway_features)

    found_gaps = []

    for i in range(len(endpoints)):

        first = endpoints[i]

        for j in range(i + 1, len(endpoints)):

            second = endpoints[j]

            # Ignore endpoints belonging to the same feature
            if first["feature_id"] == second["feature_id"]:
                continue

            distance = calculate_distance(
                first["latitude"],
                first["longitude"],
                second["latitude"],
                second["longitude"]
            )

            if distance <= MAX_ENDPOINT_GAP:

                found_gaps.append({
                    "distance": distance,
                    "first": first,
                    "second": second
                })

    found_gaps.sort(key=lambda item: item["distance"])

    if not found_gaps:
        print("No nearby endpoints found.")
        return

    for gap in found_gaps[:40]:

        first = gap["first"]
        second = gap["second"]

        print(
            f"\nGap: {gap['distance']:.1f} metres"
        )

        print(
            f"  Feature {first['feature_id']} "
            f"({first['position']}) - {first['name']}"
        )

        print(
            f"  Feature {second['feature_id']} "
            f"({second['position']}) - {second['name']}"
        )

    print(
        f"\nTotal nearby endpoint pairs found: {len(found_gaps)}"
    )


# --------------------------------------------------
# SHOW FEATURES AROUND IMPORTANT STATIONS
# --------------------------------------------------

def inspect_station_corridors(railway_features, stations):

    important_stations = [
        "Egmore",
        "Chetpet",
        "Nungambakkam",
        "Kodambakkam",
        "Mambalam",
        "Saidapet",
        "Guindy"
    ]

    print("\n" + "=" * 60)
    print("RAILWAY FEATURES AROUND EACH STATION")
    print("=" * 60)

    for station_name in important_stations:

        station_rows = stations[
            stations["location"] == station_name
        ]

        if station_rows.empty:
            continue

        station = station_rows.iloc[0]

        station_lat = float(station["latitude"])
        station_lon = float(station["longitude"])

        nearby_features = []

        for feature in railway_features:

            nearest_distance = min(
                calculate_distance(
                    station_lat,
                    station_lon,
                    point[1],
                    point[0]
                )
                for point in feature["coordinates"]
            )

            if nearest_distance <= STATION_SEARCH_RADIUS:

                nearby_features.append({
                    "id": feature["id"],
                    "name": feature["name"],
                    "distance": nearest_distance
                })

        nearby_features.sort(
            key=lambda item: item["distance"]
        )

        print(f"\n{station_name}:")

        if not nearby_features:
            print("  No nearby railway features.")
            continue

        for feature in nearby_features[:10]:

            print(
                f"  ID: {feature['id']} | "
                f"{feature['name']} | "
                f"{feature['distance']:.1f} metres"
            )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    geojson, stations = load_data()

    railway_features = extract_railway_features(geojson)

    print("\n" + "=" * 60)
    print("RAILWAY DIAGNOSTIC REPORT")
    print("=" * 60)

    print(
        "Total GeoJSON features:",
        len(geojson.get("features", []))
    )

    print(
        "Railway LineString features:",
        len(railway_features)
    )

    inspect_station_matches(
        railway_features,
        stations
    )

    inspect_endpoint_gaps(
        railway_features
    )

    inspect_station_corridors(
        railway_features,
        stations
    )

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()