import pandas as pd
import networkx as nx
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

CSV_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "metro_route_sequence.csv"
)


def build_metro_graph():

    df = pd.read_csv(CSV_PATH)

    df = df.sort_values("sequence")

    graph = nx.Graph()

    # Add Metro stations
    for _, row in df.iterrows():

        graph.add_node(
            row["station_name"],
            line=row["line_name"],
            sequence=int(row["sequence"])
        )

    # Connect consecutive stations
    stations = df["station_name"].tolist()

    for i in range(len(stations) - 1):

        graph.add_edge(
            stations[i],
            stations[i + 1],
            transport_mode="Metro"
        )

    return graph


def main():

    graph = build_metro_graph()

    print("\nCHENNAI METRO NETWORK TEST")
    print("==========================")

    print("Total stations:", graph.number_of_nodes())
    print("Total connections:", graph.number_of_edges())

    print("\nStation connections:")

    for station in graph.nodes:

        print(station, "->", list(graph.neighbors(station)))

    start = "Poonamallee Bypass"
    destination = "Vadapalani"

    route = nx.shortest_path(
        graph,
        source=start,
        target=destination
    )

    print("\nTest route:")
    print(" -> ".join(route))

    print("\nTotal stations in route:", len(route))


if __name__ == "__main__":
    main()