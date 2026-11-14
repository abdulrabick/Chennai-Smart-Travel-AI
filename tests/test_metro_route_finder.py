import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from transport_engine import find_best_route

print("\n========== METRO ROUTE FINDER TEST ==========")

# Regular fare
regular = find_best_route(
    start="Guindy",
    destination="Airport",
    priority="Fastest",
    fare_type="regular",
    transport_mode="Metro"
)

# Discounted fare
discounted = find_best_route(
    start="Guindy",
    destination="Airport",
    priority="Fastest",
    fare_type="discounted",
    transport_mode="Metro"
)

print("Regular result:", regular)
print("Discounted result:", discounted)

assert regular is not None
assert discounted is not None

assert regular["total_fare"] == 30
assert discounted["total_fare"] == 24

print("\nPASS: Regular route fare = Rs.30")
print("PASS: Discounted route fare = Rs.24")

print("\nALL ROUTE FINDER TESTS PASSED!")