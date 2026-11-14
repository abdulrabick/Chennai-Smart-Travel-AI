import sys
from pathlib import Path

import pandas as pd
import networkx as nx

BASE_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(BASE_DIR))

SEQUENCE_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "metro_line_sequences.csv"
)

df = pd.read_csv(SEQUENCE_FILE)

graph = nx.Graph()

# Build connections between consecutive stations
for line_name, group in df.groupby("line_name"):

    group = group.sort_values("sequence")

    stations = group["station_name"].tolist()

    for current, next_station in zip(
        stations,
        stations[1:]
    ):

        graph.add_edge(
            current,
            next_station,
            line=line_name
        )


print("\n========== CHENNAI METRO NETWORK TEST ==========")

print("Total stations:", graph.number_of_nodes())
print("Total connections:", graph.number_of_edges())

# Test Metro routes
test_routes = [
    ("Airport", "Wimconagar"),
    ("Airport", "St Thomas Mount"),
    ("Poonamallee Bypass", "Airport"),
]

for start, destination in test_routes:

    route = nx.shortest_path(
        graph,
        source=start,
        target=destination
    )

    print(f"\nPASS: {start} -> {destination}")
    print("Stations travelled:", len(route))
    print("Route:", " -> ".join(route))


print("\nALL METRO NETWORK TESTS PASSED!")