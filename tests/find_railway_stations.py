import requests

OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

query = """
[out:json][timeout:60];

(
  node["railway"="station"]["name"~"Chetpet|Nungambakkam|Kodambakkam|Mambalam|Saidapet|Guindy|Egmore",i]
  (12.95,80.18,13.12,80.30);

  node["public_transport"="station"]["name"~"Chetpet|Nungambakkam|Kodambakkam|Mambalam|Saidapet|Guindy|Egmore",i]
  (12.95,80.18,13.12,80.30);
);

out body;
"""

try:
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=90
    )

    response.raise_for_status()
    data = response.json()

    for station in data.get("elements", []):
        print(
            station.get("tags", {}).get("name"),
            "->",
            station["lat"],
            station["lon"]
        )

except requests.RequestException as error:
    print("OpenStreetMap error:", error)