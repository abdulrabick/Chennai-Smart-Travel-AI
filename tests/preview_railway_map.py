import json
import os
from pathlib import Path

import pandas as pd
import folium
from dotenv import load_dotenv


# =====================================================
# 1. PROJECT PATHS
# =====================================================

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

OUTPUT_FILE = (
    PROJECT_ROOT
    / "tests"
    / "railway_preview.html"
)


# =====================================================
# 2. LOAD MAPTILER API KEY
# =====================================================

load_dotenv(PROJECT_ROOT / ".env")

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")

if not MAPTILER_API_KEY:
    raise ValueError(
        "MAPTILER_API_KEY is missing. "
        "Please check your project's .env file."
    )


# =====================================================
# 3. CHECK REQUIRED FILES
# =====================================================

if not GEOJSON_FILE.exists():
    raise FileNotFoundError(
        f"Railway GeoJSON not found: {GEOJSON_FILE}"
    )

if not COORDINATES_FILE.exists():
    raise FileNotFoundError(
        f"Coordinates CSV not found: {COORDINATES_FILE}"
    )


# =====================================================
# 4. LOAD GEOJSON DATA
# =====================================================

print("Loading Chennai railway and metro tracks...")

with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
    geojson_data = json.load(file)

all_features = geojson_data["features"]

railway_features = [
    feature
    for feature in all_features
    if feature.get("properties", {}).get("railway") == "rail"
]

metro_features = [
    feature
    for feature in all_features
    if feature.get("properties", {}).get("railway") == "subway"
]

print("Local railway segments:", len(railway_features))
print("Metro segments:", len(metro_features))


# =====================================================
# 5. LOAD STATION COORDINATES
# =====================================================

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

print("Station markers loaded:", len(stations_df))


# =====================================================
# 6. CREATE MAP
# =====================================================

print("Creating Chennai map...")

travel_map = folium.Map(
    location=[13.05, 80.24],
    zoom_start=13,
    tiles=None,
    control_scale=True
)


# =====================================================
# 7. ADD MAPTILER BACKGROUND
# =====================================================

folium.TileLayer(
    tiles=(
        "https://api.maptiler.com/maps/streets-v2/"
        "{z}/{x}/{y}.png?key="
        + MAPTILER_API_KEY
    ),
    attr=(
        '&copy; <a href="https://www.maptiler.com/'
        'copyright/">MapTiler</a> '
        '&copy; <a href="https://www.openstreetmap.org/'
        'copyright">OpenStreetMap</a>'
    ),
    name="MapTiler Streets",
    overlay=False,
    control=True
).add_to(travel_map)


# =====================================================
# 8. LOCAL TRAIN TRACK LAYER
# =====================================================

railway_layer = folium.FeatureGroup(
    name="🚆 Local Train Tracks",
    show=True
)

if railway_features:

    railway_geojson = {
        "type": "FeatureCollection",
        "features": railway_features
    }

    railway_tooltip_fields = [
        field
        for field in ["name", "railway"]
        if any(
            field in feature.get("properties", {})
            for feature in railway_features
        )
    ]

    folium.GeoJson(
        railway_geojson,
        name="Local Train Tracks",
        style_function=lambda feature: {
            "color": "blue",
            "weight": 3,
            "opacity": 0.85
        },
        tooltip=(
            folium.GeoJsonTooltip(
                fields=railway_tooltip_fields
            )
            if railway_tooltip_fields
            else None
        )
    ).add_to(railway_layer)

railway_layer.add_to(travel_map)


# =====================================================
# 9. METRO TRACK LAYER
# =====================================================

metro_layer = folium.FeatureGroup(
    name="🚇 Chennai Metro Tracks",
    show=True
)

if metro_features:

    metro_geojson = {
        "type": "FeatureCollection",
        "features": metro_features
    }

    metro_tooltip_fields = [
        field
        for field in ["name", "railway"]
        if any(
            field in feature.get("properties", {})
            for feature in metro_features
        )
    ]

    folium.GeoJson(
        metro_geojson,
        name="Metro Tracks",
        style_function=lambda feature: {
            "color": "purple",
            "weight": 4,
            "opacity": 0.9
        },
        tooltip=(
            folium.GeoJsonTooltip(
                fields=metro_tooltip_fields
            )
            if metro_tooltip_fields
            else None
        )
    ).add_to(metro_layer)

metro_layer.add_to(travel_map)


# =====================================================
# 10. ADD STATION MARKERS
# =====================================================

station_layer = folium.FeatureGroup(
    name="📍 Station Markers",
    show=True
)

for _, row in stations_df.iterrows():

    station_name = str(row["location"])
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    folium.Marker(
        location=[latitude, longitude],
        tooltip=station_name,
        popup=folium.Popup(
            f"""
            <b>Station</b><br>
            Name: {station_name}<br>
            Latitude: {latitude}<br>
            Longitude: {longitude}
            """,
            max_width=250
        ),
        icon=folium.Icon(
            color="red",
            icon="train",
            prefix="fa"
        )
    ).add_to(station_layer)

station_layer.add_to(travel_map)


# =====================================================
# 11. ADD LAYER CONTROL
# =====================================================

folium.LayerControl(
    collapsed=False
).add_to(travel_map)


# =====================================================
# 12. SAVE MAP
# =====================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

travel_map.save(str(OUTPUT_FILE))


# =====================================================
# 13. SUCCESS MESSAGE
# =====================================================

print("\n===================================")
print("CHENNAI SMART TRAVEL AI")
print("===================================")

print("Map created successfully!")

print("Local railway segments:", len(railway_features))
print("Metro segments:", len(metro_features))
print("Station markers:", len(stations_df))

print("Output:", OUTPUT_FILE)

print("===================================")