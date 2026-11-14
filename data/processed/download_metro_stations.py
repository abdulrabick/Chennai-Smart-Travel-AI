import requests
import pandas as pd
from pathlib import Path
from datetime import datetime


# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    PROJECT_ROOT
    / "processed"
    / "metro_station_coordinates.csv"
)


# ==========================================
# 2. OVERPASS API
# ==========================================

ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter"
]


# Chennai bounding box:
# South, West, North, East

query = """
[out:json][timeout:120];

(
  node["railway"="station"]["station"="subway"]
    (12.85,80.05,13.20,80.35);

  node["railway"="station"]["subway"="yes"]
    (12.85,80.05,13.20,80.35);

  node["public_transport"="station"]["subway"="yes"]
    (12.85,80.05,13.20,80.35);

  node["public_transport"="platform"]["subway"="yes"]
    (12.85,80.05,13.20,80.35);

  way["railway"="station"]["station"="subway"]
    (12.85,80.05,13.20,80.35);

  way["public_transport"="station"]["subway"="yes"]
    (12.85,80.05,13.20,80.35);

  relation["public_transport"="station"]["subway"="yes"]
    (12.85,80.05,13.20,80.35);
);

out center tags;
"""


# ==========================================
# 3. DOWNLOAD DATA
# ==========================================

print("\nDOWNLOADING CHENNAI METRO STATIONS")
print("===================================")

data = None

for endpoint in ENDPOINTS:

    try:
        print(f"\nConnecting to: {endpoint}")

        response = requests.post(
            endpoint,
            data={"data": query},
            headers={
                "User-Agent": "ChennaiSmartTravelAI/1.0"
            },
            timeout=150
        )

        response.raise_for_status()

        data = response.json()

        print("Download successful!")
        break

    except Exception as error:
        print("Download failed:", error)

if data is None:
    raise RuntimeError(
        "Unable to download Metro station data. "
        "Please try again later."
    )


# ==========================================
# 4. EXTRACT STATION INFORMATION
# ==========================================

stations = []

for element in data.get("elements", []):

    tags = element.get("tags", {})

    name = tags.get("name")

    if not name:
        continue

    if element["type"] == "node":

        latitude = element.get("lat")
        longitude = element.get("lon")

    else:

        center = element.get("center", {})

        latitude = center.get("lat")
        longitude = center.get("lon")

    if latitude is None or longitude is None:
        continue

    stations.append({
        "station_name": name,
        "latitude": latitude,
        "longitude": longitude,
        "osm_type": element["type"],
        "osm_id": element["id"],
        "railway": tags.get("railway", ""),
        "station": tags.get("station", ""),
        "public_transport": tags.get(
            "public_transport", ""
        ),
        "subway": tags.get("subway", "")
    })


# ==========================================
# 5. CHECK RESULTS
# ==========================================

if not stations:
    raise ValueError(
        "No named Metro station features found. "
        "Check the OpenStreetMap query and data."
    )

stations_df = pd.DataFrame(stations)

stations_df = stations_df.drop_duplicates(
    subset=["osm_type", "osm_id"]
)


# ==========================================
# 6. SAVE CSV
# ==========================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

stations_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ==========================================
# 7. DISPLAY RESULTS
# ==========================================

print("\nCHENNAI METRO STATION RESULTS")
print("===================================")

print("Total station features:", len(stations_df))

print("\nStation names:")

for name in stations_df["station_name"]:
    print("-", name)

print("\nSaved CSV:", OUTPUT_FILE)

print("\nDownload date:", datetime.now())

print("\n===================================")
print("DOWNLOAD COMPLETE")
print("===================================")