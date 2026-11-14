import json
import math
from pathlib import Path

import networkx as nx
import pandas as pd

from shapely.geometry import LineString, Point
from shapely.ops import transform
from shapely.strtree import STRtree


# ==================================================
# 1. FILE PATHS
# ==================================================

BASE_DIR = Path(__file__).resolve().parents[1]

GEOJSON_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "chennai_railway_tracks.geojson"
)

COORDINATES_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "location_coordinates.csv"
)


# ==================================================
# 2. SETTINGS
# ==================================================

STATION_ORDER = [
    "Egmore",
    "Chetpet",
    "Nungambakkam",
    "Kodambakkam",
    "Mambalam",
    "Saidapet",
    "Guindy",
]

ENDPOINT_TOLERANCE_METRES = 5
MAX_STATION_DISTANCE_METRES = 200
MAX_SECTION_DISTANCE_KM = 8

COORDINATE_PRECISION = 7


# ==================================================
# 3. DISTANCE FUNCTION
# ==================================================

def haversine(point_a, point_b):

    lat1, lon1 = point_a
    lat2, lon2 = point_b

    radius = 6371000

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


# ==================================================
# 4. LOAD GEOJSON
# ==================================================

def load_railway_geojson():

    if not GEOJSON_FILE.exists():
        raise FileNotFoundError(
            f"GeoJSON file not found: {GEOJSON_FILE}"
        )

    with open(GEOJSON_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    features = data.get("features", [])

    print("\nGEOJSON INFORMATION")
    print("-------------------")
    print("Total features:", len(features))

    return features


# ==================================================
# 5. LOAD STATION COORDINATES
# ==================================================

def load_station_coordinates():

    if not COORDINATES_FILE.exists():
        raise FileNotFoundError(COORDINATES_FILE)

    df = pd.read_csv(COORDINATES_FILE)

    stations = {}

    for _, row in df.iterrows():

        name = str(row["location"]).strip()

        stations[name] = (
            float(row["latitude"]),
            float(row["longitude"]),
        )

    missing = [
        name
        for name in STATION_ORDER
        if name not in stations
    ]

    if missing:
        raise ValueError(
            f"Missing station coordinates: {missing}"
        )

    return stations


# ==================================================
# 6. CREATE LOCAL METRIC PROJECTION
# ==================================================

def make_projection(reference_latitude):

    def project(longitude, latitude, z=None):

        x = (
            longitude
            * 111320
            * math.cos(math.radians(reference_latitude))
        )

        y = latitude * 110540

        if z is not None:
            return x, y, z

        return x, y

    return project


# ==================================================
# 7. LOAD RAILWAY LINES
# ==================================================

def load_railway_lines(features, project):

    railway_lines = []

    invalid_count = 0

    for feature_id, feature in enumerate(features):

        properties = feature.get("properties", {})
        geometry = feature.get("geometry") or {}

        # Exclude metro/subway tracks.
        if properties.get("railway") != "rail":
            continue

        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])

        if geometry_type == "LineString":
            coordinate_groups = [coordinates]

        elif geometry_type == "MultiLineString":
            coordinate_groups = coordinates

        else:
            continue

        for group in coordinate_groups:

            cleaned = []

            for coordinate in group:

                if len(coordinate) < 2:
                    continue

                longitude = float(coordinate[0])
                latitude = float(coordinate[1])

                cleaned.append((longitude, latitude))

            if len(cleaned) < 2:
                continue

            try:

                original_line = LineString(cleaned)

                if original_line.is_empty or not original_line.is_valid:
                    invalid_count += 1
                    continue

                metric_line = transform(
                    project,
                    original_line,
                )

                if metric_line.length <= 0:
                    continue

                railway_lines.append({
                    "feature_id": feature_id,
                    "name": properties.get(
                        "name",
                        "Unnamed track",
                    ),
                    "line": metric_line,
                    "original": original_line,
                })

            except Exception:
                invalid_count += 1

    print("\nRAILWAY GEOMETRY")
    print("----------------")
    print("Valid railway lines:", len(railway_lines))
    print("Invalid lines skipped:", invalid_count)

    return railway_lines


# ==================================================
# 8. GRAPH NODE FORMAT
# ==================================================

def coordinate_key(point):

    return (
        round(point.x, COORDINATE_PRECISION),
        round(point.y, COORDINATE_PRECISION),
    )


# ==================================================
# 9. BUILD RAILWAY GRAPH
# ==================================================

def build_railway_graph(railway_lines):

    graph = nx.Graph()

    endpoint_records = []

    for line_index, item in enumerate(railway_lines):

        coordinates = list(item["line"].coords)

        # Create graph edges for every railway segment.
        for index in range(len(coordinates) - 1):

            point_a = Point(coordinates[index])
            point_b = Point(coordinates[index + 1])

            distance = point_a.distance(point_b)

            if distance <= 0:
                continue

            node_a = coordinate_key(point_a)
            node_b = coordinate_key(point_b)

            graph.add_edge(
                node_a,
                node_b,
                weight=distance,
                feature_id=item["feature_id"],
                line_index=line_index,
                connection_type="railway",
            )

        # Store the first and last points for joining
        # nearby railway segment endpoints.
        endpoint_records.append(
            (Point(coordinates[0]), line_index)
        )

        endpoint_records.append(
            (Point(coordinates[-1]), line_index)
        )

    # Find nearby endpoints using a spatial index.
    endpoint_points = [
        record[0]
        for record in endpoint_records
    ]

    tree = STRtree(endpoint_points)

    connected_count = 0

    for index, point in enumerate(endpoint_points):

        nearby_indices = tree.query(
            point.buffer(ENDPOINT_TOLERANCE_METRES)
        )

        for other_index in nearby_indices:

            other_index = int(other_index)

            if other_index <= index:
                continue

            other_point, other_line_index = (
                endpoint_records[other_index]
            )

            current_line_index = endpoint_records[index][1]

            # Do not connect endpoints belonging to
            # the same original line.
            if current_line_index == other_line_index:
                continue

            distance = point.distance(other_point)

            if distance > ENDPOINT_TOLERANCE_METRES:
                continue

            node_a = coordinate_key(point)
            node_b = coordinate_key(other_point)

            if node_a == node_b:
                continue

            graph.add_edge(
                node_a,
                node_b,
                weight=distance,
                connection_type="endpoint_join",
            )

            connected_count += 1

    components = list(
        nx.connected_components(graph)
    )

    print("\nRAILWAY GRAPH")
    print("-------------")
    print("Graph nodes:", graph.number_of_nodes())
    print("Graph edges:", graph.number_of_edges())
    print("Endpoint connections:", connected_count)
    print("Connected components:", len(components))

    return graph


# ==================================================
# 10. MATCH STATIONS AND CONNECT TO TRACK
# ==================================================

def match_stations(
    graph,
    railway_lines,
    stations,
    project,
):

    matched = {}

    print("\nSTATION TRACK MATCHING")
    print("----------------------")

    for station_name in STATION_ORDER:

        latitude, longitude = stations[station_name]

        station_point = transform(
            project,
            Point(longitude, latitude),
        )

        best_distance = float("inf")
        best_line_index = None
        best_segment_index = None
        best_projection = None

        # Find the nearest railway segment.
        for line_index, item in enumerate(railway_lines):

            coordinates = list(item["line"].coords)

            for segment_index in range(len(coordinates) - 1):

                segment_start_point = Point(
                    coordinates[segment_index]
                )

                segment_end_point = Point(
                    coordinates[segment_index + 1]
                )

                segment = LineString([
                    coordinates[segment_index],
                    coordinates[segment_index + 1],
                ])

                distance = station_point.distance(segment)

                if distance < best_distance:

                    best_distance = distance
                    best_line_index = line_index
                    best_segment_index = segment_index

                    best_projection = segment.interpolate(
                        segment.project(station_point)
                    )

        if best_projection is None:
            raise RuntimeError(
                f"No railway segment found for {station_name}"
            )

        # Get the actual graph node for the projected point.
        track_node = coordinate_key(best_projection)

        coordinates = list(
            railway_lines[best_line_index]["line"].coords
        )

        segment_start = coordinate_key(
            Point(coordinates[best_segment_index])
        )

        segment_end = coordinate_key(
            Point(coordinates[best_segment_index + 1])
        )

        # Connect the projected point to both segment ends.
        distance_to_start = best_projection.distance(
            Point(coordinates[best_segment_index])
        )

        distance_to_end = best_projection.distance(
            Point(coordinates[best_segment_index + 1])
        )

        graph.add_edge(
            track_node,
            segment_start,
            weight=distance_to_start,
            connection_type="station_track",
        )

        graph.add_edge(
            track_node,
            segment_end,
            weight=distance_to_end,
            connection_type="station_track",
        )

        # Create a separate station node.
        station_node = (
            "STATION",
            station_name,
        )

        # Connect station node to the projected track point.
        graph.add_edge(
            station_node,
            track_node,
            weight=best_distance,
            connection_type="station_connector",
        )

        matched[station_name] = {
            "coordinate": (latitude, longitude),
            "track_node": station_node,
            "distance": best_distance,
        }

        status = (
            "OK"
            if best_distance <= MAX_STATION_DISTANCE_METRES
            else "CHECK COORDINATES"
        )

        print(
            f"{station_name}: "
            f"{best_distance:.1f} metres - {status}"
        )

    return matched


# ==================================================
# 11. FIND SHORTEST RAILWAY SECTION
# ==================================================

def find_section(graph, start_node, end_node):

    try:

        path = nx.shortest_path(
            graph,
            source=start_node,
            target=end_node,
            weight="weight",
        )

        distance = nx.path_weight(
            graph,
            path,
            weight="weight",
        )

        return path, distance

    except (nx.NetworkXNoPath, nx.NodeNotFound):

        return None, None


# ==================================================
# 12. VALIDATE ADJACENT STATIONS
# ==================================================

def validate_station_sections(
    graph,
    matched_stations,
):

    print("\nADJACENT STATION ROUTE CHECK")
    print("----------------------------")

    all_valid = True
    total_distance = 0
    complete_route = []

    for index in range(len(STATION_ORDER) - 1):

        start_name = STATION_ORDER[index]
        end_name = STATION_ORDER[index + 1]

        start_info = matched_stations[start_name]
        end_info = matched_stations[end_name]

        print(f"\n{start_name} -> {end_name}")

        if (
            start_info["distance"] > MAX_STATION_DISTANCE_METRES
            or end_info["distance"] > MAX_STATION_DISTANCE_METRES
        ):

            print("FAILED: Station too far from railway line.")

            all_valid = False
            continue

        start_node = start_info["track_node"]
        end_node = end_info["track_node"]

        path, distance = find_section(
            graph,
            start_node,
            end_node,
        )

        if path is None:

            print("FAILED: No connected railway path.")

            all_valid = False
            continue

        distance_km = distance / 1000

        print("Track points:", len(path))
        print(f"Track distance: {distance_km:.2f} km")

        if distance_km > MAX_SECTION_DISTANCE_KM:

            print("WARNING: Section is unusually long.")

            all_valid = False

        else:

            print("Section distance check: OK")

        total_distance += distance

        if complete_route:
            complete_route.extend(path[1:])
        else:
            complete_route.extend(path)

    print("\nFINAL ROUTE RESULT")
    print("------------------")

    if all_valid and complete_route:

        print("Station-by-station validation: PASSED")

        print(
            "Station order:",
            " -> ".join(STATION_ORDER),
        )

        print(
            f"Total railway distance: "
            f"{total_distance / 1000:.2f} km"
        )

        print("Total graph points:", len(complete_route))

    else:

        print("Station-by-station validation: FAILED")

        print(
            "Railway geometry is not ready "
            "for map integration."
        )

    return complete_route, all_valid


# ==================================================
# 13. MAIN
# ==================================================

def main():

    print("=" * 55)
    print("CHENNAI SMART TRAVEL AI")
    print("RAILWAY NETWORK VALIDATION")
    print("=" * 55)

    features = load_railway_geojson()

    stations = load_station_coordinates()

    reference_latitude = sum(
        stations[name][0]
        for name in STATION_ORDER
    ) / len(STATION_ORDER)

    project = make_projection(reference_latitude)

    railway_lines = load_railway_lines(
        features,
        project,
    )

    if not railway_lines:
        print("No railway lines found.")
        return

    graph = build_railway_graph(railway_lines)

    matched_stations = match_stations(
        graph,
        railway_lines,
        stations,
        project,
    )

    route, is_valid = validate_station_sections(
        graph,
        matched_stations,
    )

    print("\n" + "=" * 55)

    if is_valid:
        print("RESULT: Railway route passed validation.")
    else:
        print("RESULT: Railway route needs correction.")

    print("=" * 55)


if __name__ == "__main__":
    main()