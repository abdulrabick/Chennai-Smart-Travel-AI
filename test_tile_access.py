import math
import requests

lat = 13.0787
lon = 80.2609
zoom = 13

n = 2 ** zoom

x = int((lon + 180) / 360 * n)
y = int(
    (1 - math.asinh(math.tan(math.radians(lat))) / math.pi)
    / 2 * n
)

url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"

response = requests.get(
    url,
    headers={"User-Agent": "ChennaiSmartTravelAI/1.0"},
    timeout=20
)

print("Status:", response.status_code)
print("Tile URL:", url)
print("Downloaded bytes:", len(response.content))

if response.status_code == 200:
    with open("chennai_tile.png", "wb") as file:
        file.write(response.content)

    print("Saved as chennai_tile.png")