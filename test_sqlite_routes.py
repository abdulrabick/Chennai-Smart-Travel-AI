from transport_engine import (
    find_best_route,
    compare_routes,
    find_route_within_budget
)

# Test 1: Fastest route
print("\n--- FASTEST ROUTE ---")

result = find_best_route(
    "Egmore",
    "Guindy",
    priority="Fastest"
)

print(result)


# Test 2: Compare routes
print("\n--- ROUTE COMPARISON ---")

comparison = compare_routes(
    "Egmore",
    "Guindy"
)

for priority, route in comparison.items():
    print(f"\n{priority}:")

    if route:
        print("Route:", route["route"])
        print("Fare:", route["total_fare"])
        print("Time:", route["total_time"])


# Test 3: Budget route
print("\n--- BUDGET ROUTE ---")

budget_result = find_route_within_budget(
    "Washermenpet",
    "Egmore",
    budget=50
)

print(budget_result)
from transport_engine import find_best_route

print("\n--- DISCOUNTED METRO FARE ---")

result = find_best_route(
    "Egmore",
    "Guindy",
    priority="Fastest",
    fare_type="discounted"
)

print("Route:", result["route"])
print("Fare:", result["total_fare"])
print("Time:", result["total_time"])