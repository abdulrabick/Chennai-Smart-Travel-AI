from transport_engine import find_best_route


start = "Washermenpet"
destination = "Guindy"

for priority in ["Fastest", "Cheapest", "Shortest"]:

    print(f"\n===== {priority} Route =====")

    result = find_best_route(
        start,
        destination,
        priority
    )

    if result is None:
        print("No route found.")
        continue

    print("Route:", " → ".join(result["route"]))
    print("Time:", result["total_time"], "minutes")
    print("Travel Time:", result["travel_time"], "minutes")
    print("Transfer Time:", result["total_transfer_time"], "minutes")
    print("Fare: ₹", result["total_fare"])
    print("Distance:", result["total_distance"], "km")

    for step in result["steps"]:
        print(
            step["from"],
            "→",
            step["to"],
            "|",
            step["transport"]
        )
    from transport_engine import compare_routes

start = "Washermenpet"
destination = "Guindy"

comparison = compare_routes(start, destination)

print("\n========== ROUTE COMPARISON ==========")

for priority, result in comparison.items():

    print(f"\n{priority} Route")

    if result is None:
        print("No route found.")
        continue

    print("Route:", " → ".join(result["route"]))
    print("Time:", result["total_time"], "minutes")
    print("Fare: ₹", result["total_fare"])
    print("Distance:", result["total_distance"], "km")
    from transport_engine import find_route_within_budget


start = "Washermenpet"
destination = "Guindy"
budget = 30

result = find_route_within_budget(
    start,
    destination,
    budget
)

print("\n========== BUDGET ROUTE RESULT ==========")

if result:

    print("Route:", " → ".join(result["route"]))
    print("Travel Time:", result["total_time"], "minutes")
    print("Fare: ₹", result["total_fare"])
    print("Distance:", result["total_distance"], "km")

else:

    print("No route available within your budget.")