import requests

# Egmore coordinates
start_lat = 13.0787
start_lon = 80.2609

# Guindy coordinates
end_lat = 13.0067
end_lon = 80.2206

url = (
    f"https://router.project-osrm.org/route/v1/driving/"
    f"{start_lon},{start_lat};{end_lon},{end_lat}"
)

params = {
    "overview": "full",
    "geometries": "geojson"
}

response = requests.get(
    url,
    params=params,
    timeout=20
)

response.raise_for_status()

data = response.json()

if data["code"] == "Ok":

    route = data["routes"][0]

    print("Road routing successful!")
    print("Distance:", round(route["distance"] / 1000, 2), "km")
    print("Estimated time:", round(route["duration"] / 60, 2), "minutes")

    coordinates = route["geometry"]["coordinates"]

    print("Road coordinates:", len(coordinates))

else:
    print("No road route found.")