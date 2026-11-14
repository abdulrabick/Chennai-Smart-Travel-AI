import json
import math
from pathlib import Path

import pandas as pd
from shapely.geometry import LineString, Point


# -----------------------------------------
# PROJECT PATHS
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

STATION_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "location_coordinates.csv"
)


# -----------------------------------------
# SETTINGS
# -----------------------------------------

STATION_RADIUS_METRES = 300

IMPORTANT_STATIONS = [
    "Egmore",
    "Chetpet",
    "Nungambakkam",
    "Kodambakkam",
    "Mambalam",
    "Saidapet",
    "Guindy"
]


# -----------------------------------------
# DISTANCE CALCULATION
# -----------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2):

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

    return 2 * earth_radius * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


# -----------------------------------------
# COORDINATE CONVERSION
# -----------------------------------------

def clean_coordinates(coordinates):

    result = []

    for point in coordinates:

        if not isinstance(point, (list, tuple)):
            continue

        if len(point) < 2:
            continue

        try:
            lon = float(point[0])
            lat = float(point[1])

            if not math.isfinite(lon) or not math.isfinite(lat):
                continue

            if not (-180 <= lon <= 180):
                continue

            if not (-90 <= lat <= 90):
                continue

            result.append((lon, lat))

        except (TypeError, ValueError):
            continue

    return result


def project_coordinates(coordinates, reference_lat):

    latitude_scale = 111320

    longitude_scale = (
        111320 * math.cos(math.radians(reference_lat))
    )

    return [
        (
            lon * longitude_scale,
            lat * latitude_scale
        )
        for lon, lat in coordinates
    ]


# -----------------------------------------
# LOAD RAILWAY LINES
# -----------------------------------------

def load_railway_lines():

    with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    railway_lines = []

    invalid_features = 0

    for feature_id, feature in enumerate(
        geojson.get("features", [])
    ):

        properties = feature.get("properties", {})
        geometry = feature.get("geometry")

        if not geometry:
            continue

        if properties.get("railway") != "rail":
            continue

        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])

        if geometry_type == "LineString":

            line_parts = [coordinates]

        elif geometry_type == "MultiLineString":

            line_parts = coordinates

        else:
            continue

        for part in line_parts:

            if not isinstance(part, (list, tuple)):
                invalid_features += 1
                continue

            cleaned = clean_coordinates(part)

            if len(cleaned) < 2:
                invalid_features += 1
                continue

            try:

                line = LineString(cleaned)

                if line.is_empty or not line.is_valid:
                    invalid_features += 1
                    continue

                railway_lines.append({
                    "id": feature_id,
                    "name": properties.get(
                        "name",
                        "Unnamed track"
                    ),
                    "line": line
                })

            except (ValueError, TypeError):
                invalid_features += 1

    print("\nGEOJSON LOADING REPORT")
    print("---------------------")
    print("Valid railway line segments:", len(railway_lines))
    print("Invalid segments skipped:", invalid_features)

    return railway_lines


# -----------------------------------------
# STATION TO RAILWAY DISTANCE
# -----------------------------------------

def inspect_stations(railway_lines, stations):

    print("\n" + "=" * 60)
    print("STATION TO RAILWAY LINE DISTANCE")
    print("=" * 60)

    for station_name in IMPORTANT_STATIONS:

        rows = stations[
            stations["location"] == station_name
        ]

        if rows.empty:

            print(f"\n{station_name}: Coordinates missing")
            continue

        station = rows.iloc[0]

        lat = float(station["latitude"])
        lon = float(station["longitude"])

        station_point = Point(
            *project_coordinates([(lon, lat)], lat)[0]
        )

        nearest_matches = []

        for item in railway_lines:

            projected_coordinates = project_coordinates(
                list(item["line"].coords),
                lat
            )

            projected_line = LineString(
                projected_coordinates
            )

            distance = station_point.distance(
                projected_line
            )

            nearest_matches.append({
                "id": item["id"],
                "name": item["name"],
                "distance": distance
            })

        nearest_matches.sort(
            key=lambda item: item["distance"]
        )

        print(f"\nStation: {station_name}")

        for match in nearest_matches[:5]:

            status = (
                "OK"
                if match["distance"] <= STATION_RADIUS_METRES
                else "FAR"
            )

            print(
                f"  Feature {match['id']} | "
                f"{match['name']} | "
                f"{match['distance']:.1f} m | "
                f"{status}"
            )


# -----------------------------------------
# MAMBALAM RAILWAY GEOMETRY
# -----------------------------------------

def inspect_mambalam(railway_lines, stations):

    print("\n" + "=" * 60)
    print("MAMBALAM RAILWAY GEOMETRY")
    print("=" * 60)

    rows = stations[
        stations["location"] == "Mambalam"
    ]

    if rows.empty:

        print("Mambalam coordinates not found.")
        return

    station = rows.iloc[0]

    lat = float(station["latitude"])
    lon = float(station["longitude"])

    station_point = Point(
        *project_coordinates([(lon, lat)], lat)[0]
    )

    nearby = []

    for item in railway_lines:

        projected_coordinates = project_coordinates(
            list(item["line"].coords),
            lat
        )

        projected_line = LineString(
            projected_coordinates
        )

        distance = station_point.distance(
            projected_line
        )

        if distance <= 1000:

            nearby.append({
                "id": item["id"],
                "name": item["name"],
                "distance": distance
            })

    nearby.sort(
        key=lambda item: item["distance"]
    )

    if not nearby:

        print("No railway lines found within 1 km.")
        return

    for item in nearby[:15]:

        print(
            f"Feature {item['id']} | "
            f"{item['name']} | "
            f"{item['distance']:.1f} metres"
        )


# -----------------------------------------
# RAILWAY LINE INTERSECTION CHECK
# -----------------------------------------

def inspect_track_intersections(railway_lines):

    print("\n" + "=" * 60)
    print("RAILWAY LINE INTERSECTION CHECK")
    print("=" * 60)

    reference_lat = 13.05

    projected_lines = []

    for item in railway_lines:

        coordinates = project_coordinates(
            list(item["line"].coords),
            reference_lat
        )

        projected = LineString(coordinates)

        projected_lines.append({
            "id": item["id"],
            "line": projected
        })

    intersections = 0
    near_gaps = 0

    for i in range(len(projected_lines)):

        first = projected_lines[i]

        for j in range(i + 1, len(projected_lines)):

            second = projected_lines[j]

            distance = first["line"].distance(
                second["line"]
            )

            if distance < 1:

                intersections += 1

            elif distance <= 20:

                near_gaps += 1

    print(
        "Intersecting or touching line pairs:",
        intersections
    )

    print(
        "Line pairs within 20 metres:",
        near_gaps
    )


# -----------------------------------------
# MAIN
# -----------------------------------------

def main():

    print("\nCHENNAI SMART TRAVEL AI")
    print("RAILWAY GEOMETRY DIAGNOSTIC")

    if not GEOJSON_FILE.exists():

        print("Railway GeoJSON file is missing.")
        return

    if not STATION_FILE.exists():

        print("Station coordinate CSV is missing.")
        return

    stations = pd.read_csv(STATION_FILE)

    required_columns = {
        "location",
        "latitude",
        "longitude"
    }

    if not required_columns.issubset(stations.columns):

        print("Station CSV is missing required columns.")
        return

    railway_lines = load_railway_lines()

    if not railway_lines:

        print("No valid railway lines were loaded.")
        return

    print("\nRailway lines loaded:", len(railway_lines))

    inspect_stations(
        railway_lines,
        stations
    )

    inspect_mambalam(
        railway_lines,
        stations
    )

    inspect_track_intersections(
        railway_lines
    )

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()