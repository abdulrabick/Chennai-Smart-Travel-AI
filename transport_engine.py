from pathlib import Path
import sqlite3
import heapq
from itertools import count

import pandas as pd
import networkx as nx

from metro_engine import build_metro_graph, get_metro_fare


# ==========================================
# 1. PROJECT PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "chennai_travel.db"


# ==========================================
# 2. LOAD TRANSPORT DATA
# ==========================================

def load_transport_data(fare_type="regular", transport_mode=None):

    if fare_type not in ["regular", "discounted"]:
        raise ValueError("Invalid fare type.")

    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_FILE}"
        )

    with sqlite3.connect(DATABASE_FILE) as connection:

        query = """
        SELECT
            start,
            destination,
            transport_mode,
            distance_km,
            estimated_time_min,
            estimated_fare_inr,
            transfer_time_min
        FROM transport_routes
        """

        df = pd.read_sql_query(query, connection)

    if df.empty:
        return df

    required_columns = [
        "start",
        "destination",
        "transport_mode",
        "distance_km",
        "estimated_time_min",
        "estimated_fare_inr",
        "transfer_time_min",
    ]

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing database columns: {missing}"
        )

    if transport_mode and transport_mode != "All":

        df = df[
            df["transport_mode"].astype(str).str.strip().str.casefold()
            == transport_mode.strip().casefold()
        ].copy()

    numeric_columns = [
        "distance_km",
        "estimated_time_min",
        "estimated_fare_inr",
        "transfer_time_min",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise"
        )

    return df


# ==========================================
# 3. BUILD TRANSPORT GRAPH
# ==========================================

def build_transport_graph(
    fare_type="regular",
    transport_mode=None
):

    df = load_transport_data(
        fare_type,
        transport_mode
    )

    graph = nx.MultiDiGraph()

    # NON-METRO TRANSPORT

    if not df.empty:

        for _, row in df.iterrows():

            mode = str(row["transport_mode"]).strip()

            if mode.casefold() == "metro":
                continue

            start = str(row["start"]).strip()
            destination = str(row["destination"]).strip()

            details = {
                "transport_mode": mode,
                "distance": float(row["distance_km"]),
                "time": float(row["estimated_time_min"]),
                "fare": float(row["estimated_fare_inr"]),
                "transfer_time": float(row["transfer_time_min"]),
            }

            graph.add_edge(start, destination, **details)
            graph.add_edge(destination, start, **details)

    # METRO TRANSPORT

    include_metro = (
        transport_mode is None
        or transport_mode == "All"
        or transport_mode.strip().casefold() == "metro"
    )

    if include_metro:

        metro_graph = build_metro_graph()

        for start, destination, data in metro_graph.edges(data=True):

            adjacent_fare = get_metro_fare(
                start,
                destination,
                fare_type
            )

            details = {
                "transport_mode": "Metro",
                "distance": 1.5,
                "time": float(data["estimated_minutes"]),
                "fare": adjacent_fare,
                "transfer_time": 0.0,
                "line": data["line"],
                "is_estimated": True,
            }

            graph.add_edge(start, destination, **details)
            graph.add_edge(destination, start, **details)

    return graph


# ==========================================
# 4. ROUTE WEIGHT
# ==========================================

def calculate_route_weight(data, priority):

    if priority == "Fastest":
        return data["time"] + data["transfer_time"]

    if priority == "Cheapest":
        return data["fare"]

    if priority == "Shortest":
        return data["distance"]

    raise ValueError(
        "Priority must be Fastest, Cheapest, or Shortest."
    )


# ==========================================
# 5. SELECT BEST EDGE
# ==========================================

def select_best_edge(graph, current, next_location, priority):

    edges = graph.get_edge_data(current, next_location)

    return min(
        edges.values(),
        key=lambda data: calculate_route_weight(data, priority)
    )


# ==========================================
# 6. FIND OPTIMAL PATH
# ==========================================

def find_optimal_path(
    graph,
    start,
    destination,
    priority,
    fare_type
):

    counter = count()

    start_state = (start, None)

    distances = {start_state: 0}
    previous = {}

    queue = [(0, next(counter), start_state)]

    best_cost = float("inf")
    best_state = None

    while queue:

        current_cost, _, state = heapq.heappop(queue)

        if current_cost > distances.get(state, float("inf")):
            continue

        current, metro_origin = state

        # DESTINATION REACHED

        if current == destination:

            final_cost = current_cost

            if (
                priority == "Cheapest"
                and metro_origin is not None
                and metro_origin != destination
            ):

                final_cost += get_metro_fare(
                    metro_origin,
                    destination,
                    fare_type
                )

            if final_cost < best_cost:
                best_cost = final_cost
                best_state = state

            continue

        # EXPLORE EDGES

        for _, next_location, key, data in graph.out_edges(
            current,
            keys=True,
            data=True
        ):

            mode = data["transport_mode"]

            # METRO

            if mode == "Metro":

                if priority == "Cheapest":

                    next_metro_origin = (
                        current if metro_origin is None
                        else metro_origin
                    )

                    edge_cost = 0

                else:

                    next_metro_origin = None

                    edge_cost = calculate_route_weight(
                        data,
                        priority
                    )

            # NON-METRO

            else:

                next_metro_origin = None

                edge_cost = calculate_route_weight(
                    data,
                    priority
                )

                if (
                    priority == "Cheapest"
                    and metro_origin is not None
                    and metro_origin != current
                ):

                    edge_cost += get_metro_fare(
                        metro_origin,
                        current,
                        fare_type
                    )

            new_cost = current_cost + edge_cost

            next_state = (
                next_location,
                next_metro_origin
            )

            if new_cost < distances.get(next_state, float("inf")):

                distances[next_state] = new_cost

                previous[next_state] = (state, data)

                heapq.heappush(
                    queue,
                    (new_cost, next(counter), next_state)
                )

    if best_state is None:
        return None, None

    # RECONSTRUCT PATH

    path = [best_state[0]]
    selected_edges = []

    state = best_state

    while state != start_state:

        previous_state, edge_data = previous[state]

        selected_edges.append(edge_data)

        state = previous_state

        path.append(state[0])

    path.reverse()
    selected_edges.reverse()

    return path, selected_edges


# ==========================================
# 7. BUILD ROUTE RESULT
# ==========================================

def build_route_result(
    graph,
    path,
    priority="Fastest",
    fare_type="regular",
    selected_edges=None
):

    steps = []

    total_travel_time = 0
    total_transfer_time = 0
    total_fare = 0
    total_distance = 0

    metro_segment = None

    def close_metro_segment():

        nonlocal metro_segment
        nonlocal total_fare

        if metro_segment is None:
            return

        start_station = metro_segment["from"]
        end_station = metro_segment["to"]

        if start_station != end_station:

            direct_fare = get_metro_fare(
                start_station,
                end_station,
                fare_type
            )

        else:
            direct_fare = 0.0

        metro_segment["fare"] = direct_fare

        total_fare += direct_fare

        steps.append(metro_segment)

        metro_segment = None

    # PROCESS EDGES

    for index, (current, next_location) in enumerate(
        zip(path, path[1:])
    ):

        if selected_edges is not None:
            best_edge = selected_edges[index]

        else:
            best_edge = select_best_edge(
                graph,
                current,
                next_location,
                priority
            )

        mode = best_edge["transport_mode"]

        travel_time = float(best_edge["time"])
        transfer_time = float(best_edge["transfer_time"])
        distance = float(best_edge["distance"])

        total_travel_time += travel_time
        total_transfer_time += transfer_time
        total_distance += distance

        # METRO

        if mode == "Metro":

            line = best_edge.get("line", "Metro")

            if metro_segment is None:

                metro_segment = {
                    "from": current,
                    "to": next_location,
                    "transport": "Metro",
                    "stations": [current, next_location],
                    "lines": [line],
                    "time": travel_time,
                    "transfer_time": transfer_time,
                    "fare": 0,
                    "distance": distance,
                }

            else:

                metro_segment["to"] = next_location

                metro_segment["stations"].append(next_location)

                if line not in metro_segment["lines"]:
                    metro_segment["lines"].append(line)

                metro_segment["time"] += travel_time
                metro_segment["transfer_time"] += transfer_time
                metro_segment["distance"] += distance

        # OTHER TRANSPORT

        else:

            close_metro_segment()

            fare = float(best_edge["fare"])

            total_fare += fare

            steps.append({
                "from": current,
                "to": next_location,
                "transport": mode,
                "time": travel_time,
                "transfer_time": transfer_time,
                "fare": fare,
                "distance": distance,
            })

    close_metro_segment()

    return {
        "route": path,
        "steps": steps,
        "total_time": total_travel_time + total_transfer_time,
        "travel_time": total_travel_time,
        "total_transfer_time": total_transfer_time,
        "total_fare": total_fare,
        "total_distance": total_distance,
        "fare_type": fare_type,
    }


# ==========================================
# 8. FIND BEST ROUTE
# ==========================================

def find_best_route(
    start,
    destination,
    priority="Fastest",
    fare_type="regular",
    transport_mode=None,
    traffic=None
):
    """traffic: optional ml.predictor.TrafficContext. When given, every edge time is multiplied by the
    ML-predicted delay for that hour / weekday / month / rain level (traffic-aware routing)."""

    if priority not in ["Fastest", "Cheapest", "Shortest"]:
        raise ValueError("Invalid route priority.")

    graph = build_transport_graph(
        fare_type=fare_type,
        transport_mode=transport_mode
    )

    if traffic is not None:
        from ml.predictor import adjust_graph_times
        graph = adjust_graph_times(graph, traffic)

    if start not in graph or destination not in graph:
        return None

    if start == destination:

        return {
            "route": [start],
            "steps": [],
            "total_time": 0,
            "travel_time": 0,
            "total_transfer_time": 0,
            "total_fare": 0,
            "total_distance": 0,
            "fare_type": fare_type,
        }

    path, selected_edges = find_optimal_path(
        graph=graph,
        start=start,
        destination=destination,
        priority=priority,
        fare_type=fare_type
    )

    if path is None:
        return None

    result = build_route_result(
        graph=graph,
        path=path,
        priority=priority,
        fare_type=fare_type,
        selected_edges=selected_edges
    )

    if traffic is not None:
        result["traffic"] = traffic.describe()

    return result


# ==========================================
# 9. COMPARE ROUTES
# ==========================================

def compare_routes(
    start,
    destination,
    fare_type="regular",
    transport_mode=None,
    traffic=None
):

    priorities = ["Fastest", "Cheapest", "Shortest"]

    comparison = {}

    for priority in priorities:

        comparison[priority] = find_best_route(
            start=start,
            destination=destination,
            priority=priority,
            fare_type=fare_type,
            transport_mode=transport_mode,
            traffic=traffic
        )

    return comparison


# ==========================================
# 10. ROUTE WITHIN BUDGET
# ==========================================

def find_route_within_budget(
    start,
    destination,
    budget,
    fare_type="regular",
    transport_mode=None,
    traffic=None
):

    if budget < 0:
        raise ValueError("Budget cannot be negative.")

    result = find_best_route(
        start=start,
        destination=destination,
        priority="Cheapest",
        fare_type=fare_type,
        transport_mode=transport_mode,
        traffic=traffic
    )

    if result is None or result["total_fare"] > budget:
        return None

    return result


# ==========================================
# 11. AUTOMATIC ROUTE COMPARISON TEST
# ==========================================

if __name__ == "__main__":

    print("\n" + "=" * 50)
    print("       CHENNAI SMARTROUTE AI")
    print("          ROUTE COMPARISON")
    print("=" * 50)

    START = "Airport"
    DESTINATION = "Guindy"

    print(f"\nStarting Point : {START}")
    print(f"Destination    : {DESTINATION}")

    results = compare_routes(
        start=START,
        destination=DESTINATION,
        fare_type="regular"
    )

    for priority, result in results.items():

        print("\n" + "-" * 50)
        print(f"{priority.upper()} ROUTE")
        print("-" * 50)

        if result is None:
            print("No route found.")
            continue

        print("Route:", " -> ".join(result["route"]))

        print("Transport:", ", ".join(
            step["transport"] for step in result["steps"]
        ))

        print(f"Fare: ₹{result['total_fare']:.2f}")

        print(f"Travel Time: {result['total_time']} minutes")

        print(f"Distance: {result['total_distance']} km")

        print("\nJourney Details:")

        for step in result["steps"]:
            print(step)

    print("\n" + "=" * 50)
    print("       ROUTE COMPARISON COMPLETED")
    print("=" * 50)
def find_best_journeys(
    start,
    destination,
    fare_type="regular"
):
    """Return journeys in the format expected by the Streamlit frontend."""

    comparison = compare_routes(
        start=start,
        destination=destination,
        fare_type=fare_type
    )

    recommendations = {}

    priority_mapping = {
        "Fastest": "fastest",
        "Cheapest": "cheapest",
        "Shortest": "shortest"
    }

    for priority, result_key in priority_mapping.items():

        journey = comparison.get(priority)

        if journey is None:
            recommendations[result_key] = None
            continue

        steps = journey.get("steps", [])

        transfer_count = sum(
            1
            for previous, current in zip(steps, steps[1:])
            if previous["transport"] != current["transport"]
        )

        recommendations[result_key] = {
            **journey,
            "stops": journey.get("route", []),
            "route": steps,
            "transfer_count": transfer_count,
            "transfer_time": journey.get(
                "total_transfer_time", 0
            )
        }

    return recommendations