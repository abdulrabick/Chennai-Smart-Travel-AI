import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from transport_engine import (
    build_transport_graph,
    find_best_route
)

print("\n========== INDIVIDUAL TRANSPORT ROUTE TEST ==========")

graph = build_transport_graph()

modes = sorted({
    data["transport_mode"]
    for _, _, data in graph.edges(data=True)
})

for mode in modes:

    # Find one sample connection for this mode
    sample = next(
        (
            (start, destination)
            for start, destination, data in graph.edges(data=True)
            if data["transport_mode"] == mode
        ),
        None
    )

    if sample is None:
        print("FAIL:", mode, "- No connection found")
        continue

    start, destination = sample

    result = find_best_route(
        start,
        destination,
        priority="Fastest",
        transport_mode=mode
    )

    if result is None:
        print("FAIL:", mode, "-", start, "->", destination)
    else:
        print("\nPASS:", mode)
        print("Journey:", start, "->", destination)
        print("Fare: Rs.", result["total_fare"])
        print("Time:", result["total_time"], "minutes")

print("\nINDIVIDUAL TRANSPORT TEST COMPLETED!")