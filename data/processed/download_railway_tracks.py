import json
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

# Chennai railway network area
SOUTH = 12.95
WEST = 80.18
NORTH = 13.12
EAST = 80.30

query = f"""
[out:json][timeout:90];

(
    way["railway"="rail"]
    ({SOUTH},{WEST},{NORTH},{EAST});

    way["railway"="subway"]
    ({SOUTH},{WEST},{NORTH},{EAST});
);

out geom;
"""

print("Downloading Chennai railway tracks...")

try:
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={
            "User-Agent": "ChennaiSmartTravelAI/1.0"
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    features = []

    for element in data.get("elements", []):

        if element.get("type") != "way":
            continue

        geometry = element.get("geometry", [])

        if len(geometry) < 2:
            continue

        coordinates = [
            [point["lon"], point["lat"]]
            for point in geometry
        ]

        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": element["id"],
                "railway": element.get("tags", {}).get("railway"),
                "name": element.get("tags", {}).get("name", "Unnamed track")
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(geojson, file, indent=2)

    print("Download successful!")
    print("Railway track segments:", len(features))
    print("Saved to:", OUTPUT_FILE)

except requests.RequestException as error:
    print("Download failed:", error)