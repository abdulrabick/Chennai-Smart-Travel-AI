import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

features = data["features"]

print("Total railway segments:", len(features))

print("\nRAILWAY TYPE COUNTS")
print("------------------------------")

railway_types = Counter()

for feature in features:
    railway = feature["properties"].get("railway", "Unknown")
    railway_types[railway] += 1

for name, count in railway_types.items():
    print(name, ":", count)


print("\nTRACK NAME COUNTS")
print("------------------------------")

track_names = Counter()

for feature in features:
    name = feature["properties"].get("name") or "Unnamed track"
    track_names[name] += 1

for name, count in track_names.most_common():
    print(name, ":", count)


print("\nGEOMETRY VERIFICATION")
print("------------------------------")

valid_segments = sum(
    1
    for feature in features
    if feature["geometry"]
    and len(feature["geometry"]["coordinates"]) >= 2
)

print("Valid railway segments:", valid_segments)