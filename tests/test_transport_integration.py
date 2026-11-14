import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from transport_engine import (
    build_transport_graph,
    find_best_route,
    compare_routes,
)


print("\n========== TRANSPORT INTEGRATION TEST ==========")


# Test 1: Metro graph
graph = build_transport_graph(
    transport_mode="Metro"
)

print("\nTEST 1: METRO NETWORK")

print("Total Metro stations:", graph.number_of_nodes())
print("Total Metro connections:", graph.number_of_edges())

assert "Airport" in graph
assert "Wimconagar" in graph

print("PASS: Complete Metro network loaded.")


# Test 2: Metro journey
print("\nTEST 2: AIRPORT TO WIMCONAGAR")

result = find_best_route(
    "Airport",
    "Wimconagar",
    priority="Fastest",
    fare_type="regular",
    transport_mode="Metro"
)

assert result is not None

print("Route:", " -> ".join(result["route"]))
print("Stops:", len(result["route"]) - 1)
print("Estimated time:", result["total_time"])
print("Fare:", result["total_fare"])

assert result["total_fare"] == 50

print("PASS: Metro journey fare calculated.")


# Test 3: Multi-station fare
print("\nTEST 3: EGMO​​RE TO AIRPORT")

result = find_best_route(
    "Egmore",
    "Airport",
    priority="Fastest",
    fare_type="regular",
    transport_mode="Metro"
)

assert result is not None
assert result["total_fare"] == 40

print("Fare:", result["total_fare"])
print("PASS: Direct CMRL fare applied.")


# Test 4: Discounted fare
print("\nTEST 4: DISCOUNTED FARE")

result = find_best_route(
    "Egmore",
    "Airport",
    priority="Fastest",
    fare_type="discounted",
    transport_mode="Metro"
)

assert result is not None
assert result["total_fare"] == 32

print("Discounted fare:", result["total_fare"])
print("PASS: Discounted fare applied.")


# Test 5: Route comparison
print("\nTEST 5: ROUTE COMPARISON")

comparison = compare_routes(
    "Airport",
    "Guindy",
    fare_type="regular",
    transport_mode="Metro"
)

for priority, route_result in comparison.items():

    if route_result:
        print(
            priority,
            "-> Fare:",
            route_result["total_fare"],
            "| Time:",
            route_result["total_time"]
        )

print("\nALL TRANSPORT INTEGRATION TESTS COMPLETED!")