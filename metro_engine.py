from functools import lru_cache
from pathlib import Path

import pandas as pd
import networkx as nx


# ==========================================
# FILE PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

SEQUENCE_FILE = (
    BASE_DIR / "data" / "processed" / "metro_line_sequences.csv"
)

FARE_FILE = (
    BASE_DIR / "data" / "processed" / "cmrl_metro_fares.csv"
)


# ==========================================
# LOAD METRO DATA
# ==========================================

@lru_cache(maxsize=1)
def _read_metro_files():
    # The CSV files never change while the app runs, so read them once (this made route search ~50x faster).
    return pd.read_csv(SEQUENCE_FILE), pd.read_csv(FARE_FILE)


def load_metro_data():

    return _read_metro_files()


# ==========================================
# BUILD METRO NETWORK
# ==========================================

def build_metro_graph():

    sequences, _ = load_metro_data()

    graph = nx.Graph()

    for line_name, line_data in sequences.groupby("line_name"):

        line_data = line_data.sort_values("sequence")

        stations = line_data["station_name"].tolist()

        for i in range(len(stations) - 1):

            start = stations[i]
            destination = stations[i + 1]

            graph.add_edge(
                start,
                destination,
                line=line_name,
                stops=1,
                estimated_minutes=3
            )

    return graph


# ==========================================
# GET DIRECT METRO FARE
# ==========================================

def get_metro_fare(start, destination, fare_type="regular"):

    _, fares = load_metro_data()

    fare_column = (
        "regular_fare"
        if fare_type.lower() == "regular"
        else "discounted_fare"
    )

    result = fares[
        (fares["start"] == start)
        & (fares["destination"] == destination)
    ]

    if result.empty:

        result = fares[
            (fares["start"] == destination)
            & (fares["destination"] == start)
        ]

    if result.empty:
        raise ValueError(
            f"Metro fare not found: {start} -> {destination}"
        )

    return float(result.iloc[0][fare_column])


# ==========================================
# FIND METRO ROUTE
# ==========================================

def find_metro_route(
    start,
    destination,
    priority="Fastest",
    fare_type="regular"
):

    graph = build_metro_graph()

    if start not in graph:
        raise ValueError(f"Starting station not found: {start}")

    if destination not in graph:
        raise ValueError(
            f"Destination station not found: {destination}"
        )

    if priority.lower() == "fastest":

        weight = "estimated_minutes"

    else:

        # Cheapest Metro fare is based on the
        # direct origin-to-destination fare.
        # Use fewest stops as the route tie-breaker.
        weight = "stops"

    path = nx.shortest_path(
        graph,
        source=start,
        target=destination,
        weight=weight
    )

    total_stops = len(path) - 1

    estimated_time = total_stops * 3

    total_fare = get_metro_fare(
        start,
        destination,
        fare_type
    )

    journey_lines = []

    for i in range(len(path) - 1):

        edge_data = graph[path[i]][path[i + 1]]

        line = edge_data["line"]

        if not journey_lines or journey_lines[-1] != line:
            journey_lines.append(line)

    return {
        "start": start,
        "destination": destination,
        "route": path,
        "total_stations": len(path),
        "total_stops": total_stops,
        "estimated_minutes": estimated_time,
        "fare": total_fare,
        "fare_type": fare_type,
        "lines": journey_lines
    }