import sys
from pathlib import Path

# Add project root to Python import path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from transport_engine import load_transport_data

print("\n========== METRO ENGINE FARE TEST ==========")

# Test regular fare
regular = load_transport_data(
    fare_type="regular",
    transport_mode="Metro"
)

# Test discounted fare
discounted = load_transport_data(
    fare_type="discounted",
    transport_mode="Metro"
)

# Find Guindy -> Airport
regular_route = regular[
    (regular["start"] == "Guindy") &
    (regular["destination"] == "Airport")
]

discounted_route = discounted[
    (discounted["start"] == "Guindy") &
    (discounted["destination"] == "Airport")
]

assert len(regular_route) == 1, "Regular route not found"
assert len(discounted_route) == 1, "Discounted route not found"

assert regular_route.iloc[0]["estimated_fare_inr"] == 30
assert discounted_route.iloc[0]["estimated_fare_inr"] == 24

print("PASS: Regular Metro fare = Rs.30")
print("PASS: Discounted Metro fare = Rs.24")

print("\nMETRO ENGINE TEST PASSED!")