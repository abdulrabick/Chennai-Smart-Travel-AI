import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

print("\nCHENNAI METRO STATION INSPECTION")
print("================================")

count = 0

for feature in data["features"]:

    properties = feature.get("properties", {})

    railway = properties.get("railway")
    station = properties.get("station")
    public_transport = properties.get("public_transport")

    if (
        railway == "station"
        or station == "subway"
        or public_transport == "station"
    ):

        geometry = feature.get("geometry", {})

        print("\nStation:", properties.get("name", "Unnamed"))
        print("Railway:", railway)
        print("Station type:", station)
        print("Public transport:", public_transport)
        print("Geometry:", geometry.get("type"))

        count += 1

print("\n================================")
print("Total station features:", count)
print("INSPECTION COMPLETE")