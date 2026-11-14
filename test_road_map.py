import requests
import folium

start = (13.0787, 80.2609)       # Egmore
destination = (13.0067, 80.2206)  # Guindy

url = (
    "https://router.project-osrm.org/route/v1/driving/"
    f"{start[1]},{start[0]};{destination[1]},{destination[0]}"
)

response = requests.get(
    url,
    params={"overview": "full", "geometries": "geojson"},
    timeout=20
)
response.raise_for_status()

data = response.json()

if data["code"] != "Ok":
    raise Exception("Road route not found")

route = data["routes"][0]

road_coordinates = [
    [lat, lon]
    for lon, lat in route["geometry"]["coordinates"]
]

# Create interactive map with OpenStreetMap
road_map = folium.Map(
    location=start,
    zoom_start=13,
    tiles="OpenStreetMap"
)

# Draw actual road route
folium.PolyLine(
    road_coordinates,
    color="blue",
    weight=6,
    tooltip="Egmore to Guindy"
).add_to(road_map)

folium.Marker(
    start,
    tooltip="Egmore",
    icon=folium.Icon(color="green")
).add_to(road_map)

folium.Marker(
    destination,
    tooltip="Guindy",
    icon=folium.Icon(color="red")
).add_to(road_map)

road_map.fit_bounds(road_coordinates)

road_map.save("test_road_map.html")

print("Interactive map created!")
print("Distance:", round(route["distance"] / 1000, 2), "km")
print("Time:", round(route["duration"] / 60, 2), "minutes")