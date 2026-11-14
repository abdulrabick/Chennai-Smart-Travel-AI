import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from metro_engine import find_metro_route

result = find_metro_route(
    "Egmore",
    "Airport",
    priority="Fastest",
    fare_type="discounted"
)

print("\n========== DISCOUNTED METRO FARE TEST ==========")
print("Journey:", result["start"], "->", result["destination"])
print("Regular/discounted fare type:", result["fare_type"])
print("Discounted fare: Rs.", result["fare"])

print("\nDISCOUNTED FARE TEST COMPLETED!")