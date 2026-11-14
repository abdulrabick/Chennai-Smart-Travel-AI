import json
from pathlib import Path

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, nearest_points, unary_union


# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

COORDINATES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "location_coordinates.csv"
)


# ==========================================
# 2. METRO STATION CANDIDATES
# ==========================================

METRO_STATIONS = [
    "Washermenpet",
    "Chennai Central",
    "Egmore",
    "Airport"
]


# ==========================================
# 3. LOAD METRO TRACKS
# ==========================================

print("\nLOADING CHENNAI METRO TRACKS")

with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

metro_lines = []

for feature in data["features"]:

    properties = feature.get("properties", {})

    if properties.get("railway") != "subway":
        continue

    geometry = shape(feature["geometry"])

    if geometry.geom_type == "LineString":
        metro_lines.append(geometry)

print("Metro track segments:", len(metro_lines))


# ==========================================
# 4. COORDINATE PROJECTION
# ==========================================

projector = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:32644",
    always_xy=True
)

inverse_projector = Transformer.from_crs(
    "EPSG:32644",
    "EPSG:4326",
    always_xy=True
)


def project_geometry(geometry):
    return transform(
        projector.transform,
        geometry
    )


projected_lines = [
    project_geometry(line)
    for line in metro_lines
]

if not projected_lines:
    raise ValueError("No Metro track geometry found.")

metro_network = unary_union(projected_lines)


# ==========================================
# 5. LOAD STATION COORDINATES
# ==========================================

stations_df = pd.read_csv(COORDINATES_FILE)

required_columns = {
    "location",
    "latitude",
    "longitude"
}

missing_columns = required_columns - set(stations_df.columns)

if missing_columns:
    raise ValueError(
        f"Missing CSV columns: {missing_columns}"
    )

print("\nCHECKING METRO STATION COORDINATES")


# ==========================================
# 6. MATCH STATIONS TO METRO TRACKS
# ==========================================

for station_name in METRO_STATIONS:

    station = stations_df[
        stations_df["location"].astype(str).str.lower()
        == station_name.lower()
    ]

    if station.empty:
        print(f"\n{station_name}: NOT FOUND IN CSV")
        continue

    row = station.iloc[0]

    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    station_point = Point(
        longitude,
        latitude
    )

    projected_station = project_geometry(
        station_point
    )

    # Find nearest Metro track point
    nearest_track_point = nearest_points(
        metro_network,
        projected_station
    )[0]

    # Convert nearest point back to latitude/longitude
    nearest_longitude, nearest_latitude = (
        inverse_projector.transform(
            nearest_track_point.x,
            nearest_track_point.y
        )
    )

    # Calculate distance in metres
    distance = projected_station.distance(
        nearest_track_point
    )

    print(f"\nStation: {station_name}")

    print(
        f"  Existing coordinate: "
        f"{latitude:.6f}, {longitude:.6f}"
    )

    print(
        f"  Nearest track coordinate: "
        f"{nearest_latitude:.6f}, "
        f"{nearest_longitude:.6f}"
    )

    print(
        f"  Distance from Metro track: "
        f"{distance:.1f} metres"
    )

    if distance <= 100:
        print("  STATUS: CLOSE TO TRACK")
    else:
        print("  STATUS: NEEDS COORDINATE VERIFICATION")


# ==========================================
# 7. FINAL RESULT
# ==========================================

print("\n===================================")
print("CHENNAI METRO VALIDATION COMPLETE")
print("===================================")