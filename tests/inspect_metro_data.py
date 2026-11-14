import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

metro_features = []

for feature in data.get("features", []):

    properties = feature.get("properties", {})

    if properties.get("railway") == "subway":
        metro_features.append(feature)

print("\nCHENNAI METRO DATA")
print("------------------")

print("Total Metro features:", len(metro_features))

print("\nMETRO TRACK NAMES")

names = Counter(
    feature.get("properties", {}).get(
        "name", "Unnamed"
    )
    for feature in metro_features
)

for name, count in names.items():
    print(f"{name}: {count} segments")

print("\nMETRO GEOMETRY TYPES")

geometry_types = Counter(
    feature.get("geometry", {}).get("type", "Unknown")
    for feature in metro_features
)

for geometry_type, count in geometry_types.items():
    print(f"{geometry_type}: {count}")

print("\nINSPECTION COMPLETE")