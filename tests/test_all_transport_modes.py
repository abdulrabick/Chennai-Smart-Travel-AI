import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from transport_engine import build_transport_graph


print("\n========== ALL TRANSPORT MODES TEST ==========")

graph = build_transport_graph()

modes = set()

for _, _, data in graph.edges(data=True):
    modes.add(data["transport_mode"])

print("\nAvailable transport modes:")

for mode in sorted(modes):
    print("PASS:", mode)

print("\nTotal locations:", graph.number_of_nodes())
print("Total connections:", graph.number_of_edges())

print("\nALL TRANSPORT MODES LOADED!")