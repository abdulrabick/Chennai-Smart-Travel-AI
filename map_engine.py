from pathlib import Path
from functools import lru_cache
import math

import pandas as pd
import folium
import requests
import networkx as nx

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


# =====================================================
# 1. PROJECT PATHS
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

COORDINATES_FILE = (
    BASE_DIR / "data" / "processed" / "location_coordinates.csv"
)

RAILWAY_FILE = (
    BASE_DIR / "data" / "processed" / "chennai_railway_tracks.geojson"
)

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"

ENDPOINT_TOLERANCE_METRES = 5
COORDINATE_PRECISION = 7


# =====================================================
# 2. TRANSPORT CONFIGURATION
# =====================================================

TRANSPORT_COLORS = {
    "Local Train": "blue",
    "Metro": "purple",
    "MTC Bus": "orange",
    "Share Auto": "green",
    "Rapido Bike Taxi": "red",
    "Cab": "darkblue",
    "Pink Auto": "pink",
}

ROAD_TRANSPORT_MODES = {
    "share auto",
    "rapido bike taxi",
    "cab",
    "pink auto",
}


# =====================================================
# 3. LOAD LOCATION COORDINATES
# =====================================================

def load_location_coordinates():

    if not COORDINATES_FILE.exists():
        raise FileNotFoundError(
            f"Coordinates file not found: {COORDINATES_FILE}"
        )

    df = pd.read_csv(COORDINATES_FILE)

    required_columns = {
        "location",
        "latitude",
        "longitude",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing coordinate columns: {missing}"
        )

    coordinates = {}

    for _, row in df.iterrows():

        location = str(row["location"]).strip()

        coordinates[location] = [
            float(row["latitude"]),
            float(row["longitude"]),
        ]

    return coordinates


# =====================================================
# 4. ROAD ROUTING USING OSRM
# =====================================================

@lru_cache(maxsize=200)
def get_road_coordinates(start_point, end_point):

    url = (
        f"{OSRM_URL}"
        f"{start_point[1]},{start_point[0]};"
        f"{end_point[1]},{end_point[0]}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "ChennaiSmartTravelAI/1.0"
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            return None

        raw_coordinates = (
            data["routes"][0]["geometry"]["coordinates"]
        )

        return [
            [lat, lon]
            for lon, lat in raw_coordinates
        ]

    except (
        requests.RequestException,
        KeyError,
        IndexError,
        ValueError,
    ) as error:

        print("OSRM ERROR:", error)

        return None


# =====================================================
# 5. LOCAL METRIC PROJECTION
# =====================================================

def make_projection(reference_latitude):

    def project(longitude, latitude):

        x = (
            longitude
            * 111320
            * math.cos(math.radians(reference_latitude))
        )

        y = latitude * 110540

        return x, y

    return project


def coordinate_key(x, y):

    return (
        round(x, COORDINATE_PRECISION),
        round(y, COORDINATE_PRECISION),
    )


# =====================================================
# 6. BUILD RAILWAY GRAPH
# =====================================================

@lru_cache(maxsize=1)
def load_railway_network():

    if not RAILWAY_FILE.exists():

        raise FileNotFoundError(
            f"Railway GeoJSON not found: {RAILWAY_FILE}"
        )

    import json

    coordinates = load_location_coordinates()

    reference_latitude = sum(
        point[0] for point in coordinates.values()
    ) / len(coordinates)

    project = make_projection(reference_latitude)

    with open(
        RAILWAY_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    railway_lines = []

    graph = nx.Graph()

    endpoint_records = []

    for feature_id, feature in enumerate(
        data.get("features", [])
    ):

        properties = feature.get("properties", {})

        # Use railway=rail only.
        # Metro/subway is handled separately later.

        if properties.get("railway") != "rail":
            continue

        geometry = feature.get("geometry") or {}

        geometry_type = geometry.get("type")

        raw_coordinates = geometry.get("coordinates", [])

        if geometry_type == "LineString":

            groups = [raw_coordinates]

        elif geometry_type == "MultiLineString":

            groups = raw_coordinates

        else:

            continue

        for group in groups:

            metric_coordinates = []

            original_coordinates = []

            for coordinate in group:

                if len(coordinate) < 2:
                    continue

                longitude = float(coordinate[0])
                latitude = float(coordinate[1])

                x, y = project(
                    longitude,
                    latitude,
                )

                metric_coordinates.append((x, y))

                original_coordinates.append(
                    (latitude, longitude)
                )

            if len(metric_coordinates) < 2:
                continue

            line = LineString(metric_coordinates)

            if line.is_empty or not line.is_valid:
                continue

            if line.length <= 0:
                continue

            line_index = len(railway_lines)

            railway_lines.append({
                "line": line,
                "original": original_coordinates,
                "feature_id": feature_id,
            })

            # Add railway track segments to graph.

            for index in range(
                len(metric_coordinates) - 1
            ):

                point_a = Point(
                    metric_coordinates[index]
                )

                point_b = Point(
                    metric_coordinates[index + 1]
                )

                distance = point_a.distance(point_b)

                if distance <= 0:
                    continue

                node_a = coordinate_key(
                    point_a.x,
                    point_a.y,
                )

                node_b = coordinate_key(
                    point_b.x,
                    point_b.y,
                )

                graph.add_edge(
                    node_a,
                    node_b,
                    weight=distance,
                )

            # Save endpoints for joining nearby lines.

            endpoint_records.append(
                (
                    Point(metric_coordinates[0]),
                    line_index,
                )
            )

            endpoint_records.append(
                (
                    Point(metric_coordinates[-1]),
                    line_index,
                )
            )

    # Connect nearby endpoints.

    endpoint_points = [
        record[0]
        for record in endpoint_records
    ]

    if endpoint_points:

        tree = STRtree(endpoint_points)

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

                current_line_index = (
                    endpoint_records[index][1]
                )

                if current_line_index == other_line_index:
                    continue

                distance = point.distance(other_point)

                if distance > ENDPOINT_TOLERANCE_METRES:
                    continue

                node_a = coordinate_key(
                    point.x,
                    point.y,
                )

                node_b = coordinate_key(
                    other_point.x,
                    other_point.y,
                )

                if node_a == node_b:
                    continue

                graph.add_edge(
                    node_a,
                    node_b,
                    weight=distance,
                )

    print("\nRAILWAY NETWORK LOADED")
    print("----------------------")
    print("Railway lines:", len(railway_lines))
    print("Graph nodes:", graph.number_of_nodes())
    print("Graph edges:", graph.number_of_edges())

    return railway_lines, graph, project


# =====================================================
# 7. MATCH STATIONS TO RAILWAY TRACKS
# =====================================================

def connect_station_to_track(
    graph,
    railway_lines,
    station_name,
    station_coordinate,
    project,
):

    latitude, longitude = station_coordinate

    x, y = project(
        longitude,
        latitude,
    )

    station_point = Point(x, y)

    best_distance = float("inf")
    best_projection = None
    best_line_index = None
    best_segment_index = None

    # Find the nearest railway segment.

    for line_index, item in enumerate(railway_lines):

        coordinates = list(item["line"].coords)

        for segment_index in range(
            len(coordinates) - 1
        ):

            segment = LineString([
                coordinates[segment_index],
                coordinates[segment_index + 1],
            ])

            distance = station_point.distance(segment)

            if distance < best_distance:

                best_distance = distance

                best_projection = segment.interpolate(
                    segment.project(station_point)
                )

                best_line_index = line_index

                best_segment_index = segment_index

    if best_projection is None:
        return None

    if best_distance > 200:
        print(
            f"WARNING: {station_name} is "
            f"{best_distance:.1f} metres from railway track."
        )

        return None

    track_node = coordinate_key(
        best_projection.x,
        best_projection.y,
    )

    coordinates = list(
        railway_lines[best_line_index]["line"].coords
    )

    segment_start = Point(
        coordinates[best_segment_index]
    )

    segment_end = Point(
        coordinates[best_segment_index + 1]
    )

    # Connect projected station position to track endpoints.

    graph.add_edge(
        track_node,
        coordinate_key(
            segment_start.x,
            segment_start.y,
        ),
        weight=best_projection.distance(segment_start),
    )

    graph.add_edge(
        track_node,
        coordinate_key(
            segment_end.x,
            segment_end.y,
        ),
        weight=best_projection.distance(segment_end),
    )

    station_node = (
        "STATION",
        station_name,
    )

    graph.add_edge(
        station_node,
        track_node,
        weight=best_distance,
    )

    print(
        f"{station_name}: "
        f"{best_distance:.1f} metres from railway"
    )

    return station_node


# =====================================================
# 8. GET ACTUAL LOCAL TRAIN ROUTE
# =====================================================

def get_railway_coordinates(
    start_name,
    end_name,
    coordinates,
):

    try:

        railway_lines, base_graph, project = (
            load_railway_network()
        )

        # Copy graph because station connections are dynamic.

        graph = base_graph.copy()

        start_node = connect_station_to_track(
            graph,
            railway_lines,
            start_name,
            coordinates[start_name],
            project,
        )

        end_node = connect_station_to_track(
            graph,
            railway_lines,
            end_name,
            coordinates[end_name],
            project,
        )

        if start_node is None or end_node is None:
            return None

        path = nx.shortest_path(
            graph,
            source=start_node,
            target=end_node,
            weight="weight",
        )

        # Convert metric graph points to latitude/longitude.

        reference_latitude = sum(
            point[0]
            for point in coordinates.values()
        ) / len(coordinates)

        result = []

        for node in path:

            if (
                isinstance(node, tuple)
                and len(node) == 2
                and node[0] == "STATION"
            ):

                continue

            x, y = node

            longitude = (
                x
                / (
                    111320
                    * math.cos(
                        math.radians(reference_latitude)
                    )
                )
            )

            latitude = y / 110540

            result.append([
                latitude,
                longitude,
            ])

        if len(result) < 2:
            return None

        print(
            f"RAILWAY ROUTE: {start_name} -> {end_name}"
        )

        print("Railway route points:", len(result))

        return result

    except (
        nx.NetworkXNoPath,
        nx.NodeNotFound,
        ValueError,
        KeyError,
    ) as error:

        print("RAILWAY ROUTING ERROR:", error)

        return None


# =====================================================
# 9. CREATE ROUTE MAP
# =====================================================

def create_route_map(route, steps):

    coordinates = load_location_coordinates()

    missing_locations = [
        location
        for location in route
        if location not in coordinates
    ]

    if missing_locations:

        raise ValueError(
            f"Coordinates missing for: {missing_locations}"
        )

    route_coordinates = [
        coordinates[location]
        for location in route
    ]

    if not route_coordinates:
        raise ValueError("Route has no locations.")

    center_lat = sum(
        point[0] for point in route_coordinates
    ) / len(route_coordinates)

    center_lon = sum(
        point[1] for point in route_coordinates
    ) / len(route_coordinates)

    route_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    all_map_coordinates = []

    routing_warnings = []

    # =================================================
    # 10. DRAW TRANSPORT SEGMENTS
    # =================================================

    for step in steps:

        start_name = step["from"]
        end_name = step["to"]

        start_point = coordinates[start_name]
        end_point = coordinates[end_name]

        transport = str(
            step["transport"]
        ).strip()

        color = TRANSPORT_COLORS.get(
            transport,
            "gray",
        )

        popup_text = f"""
        <div style="width:220px">
            <b>{start_name} → {end_name}</b><br><br>
            <b>Transport:</b> {transport}<br>
            <b>Fare:</b> ₹{step['fare']}<br>
            <b>Time:</b> {step['time']} minutes<br>
            <b>Distance:</b> {step['distance']} km
        </div>
        """

        segment_coordinates = None

        # ---------------------------------------------
        # ROAD VEHICLES
        # ---------------------------------------------

        if transport.casefold() in ROAD_TRANSPORT_MODES:

            segment_coordinates = get_road_coordinates(
                tuple(start_point),
                tuple(end_point),
            )

            if not segment_coordinates:

                routing_warnings.append(
                    f"{transport}: {start_name} to {end_name}"
                )

        # ---------------------------------------------
        # LOCAL TRAIN - ACTUAL RAILWAY GEOMETRY
        # ---------------------------------------------

        elif transport.casefold() == "local train":

            segment_coordinates = get_railway_coordinates(
                start_name,
                end_name,
                coordinates,
            )

            if not segment_coordinates:

                routing_warnings.append(
                    f"Local Train: {start_name} to {end_name}"
                )

        # ---------------------------------------------
        # METRO AND MTC BUS
        # ---------------------------------------------

        else:

            # Approximate transit geometry for now.

            segment_coordinates = [
                start_point,
                end_point,
            ]

        # ---------------------------------------------
        # DRAW AVAILABLE ROUTE
        # ---------------------------------------------

        if segment_coordinates:

            is_approximate = (
                transport.casefold() in {
                    "metro",
                    "mtc bus",
                }
            )

            folium.PolyLine(
                locations=segment_coordinates,
                color=color,
                weight=7,
                opacity=0.9,
                dash_array=(
                    "8, 8"
                    if is_approximate
                    else None
                ),
                tooltip=(
                    f"{transport}: "
                    f"{start_name} → {end_name}"
                ),
                popup=folium.Popup(
                    popup_text,
                    max_width=300,
                ),
            ).add_to(route_map)

            all_map_coordinates.extend(
                segment_coordinates
            )

    # =================================================
    # 11. ADD LOCATION MARKERS
    # =================================================

    for index, location in enumerate(route):

        point = coordinates[location]

        if index == 0:

            marker_color = "green"
            label = "START"

        elif index == len(route) - 1:

            marker_color = "red"
            label = "DESTINATION"

        else:

            marker_color = "blue"
            label = "TRANSFER"

        folium.Marker(
            location=point,
            popup=f"{label}: {location}",
            tooltip=f"{label}: {location}",
            icon=folium.Icon(
                color=marker_color,
                icon="map-marker",
                prefix="fa",
            ),
        ).add_to(route_map)

    # =================================================
    # 12. ROUTING WARNINGS
    # =================================================

    if routing_warnings:

        warning_html = """
        <div style="
            position: fixed;
            top: 15px;
            right: 15px;
            background: #fff3cd;
            padding: 12px;
            border: 1px solid #856404;
            border-radius: 8px;
            z-index: 9999;
            max-width: 280px;
            font-size: 13px;
        ">
            <b>Routing warning</b><br>
            Some routes could not be calculated.
            Check the terminal for details.
        </div>
        """

        route_map.get_root().html.add_child(
            folium.Element(warning_html)
        )

    # =================================================
    # 13. FIT MAP TO ROUTE
    # =================================================

    if all_map_coordinates:

        route_map.fit_bounds(
            all_map_coordinates,
            padding=(40, 40),
        )

    # =================================================
    # 14. TRANSPORT LEGEND
    # =================================================

    legend_html = """
    <div style="
        position: fixed;
        bottom: 25px;
        left: 25px;
        width: 220px;
        background-color: white;
        border: 2px solid #555;
        z-index: 9999;
        padding: 12px;
        font-size: 13px;
        border-radius: 10px;
        box-shadow: 2px 2px 6px #888;
    ">

        <b>CHENNAI SMART TRAVEL AI</b>
        <hr>

        <b>Transport Modes</b><br>

        <span style="color:blue;">●</span> Local Train<br>
        <span style="color:purple;">●</span> Metro<br>
        <span style="color:orange;">●</span> MTC Bus<br>
        <span style="color:green;">●</span> Share Auto<br>
        <span style="color:red;">●</span> Rapido Bike Taxi<br>
        <span style="color:darkblue;">●</span> Cab<br>
        <span style="color:#e83e8c;">●</span> Pink Auto<br>

        <hr>

        <b>Journey Markers</b><br>

        <span style="color:green;">●</span> Start<br>
        <span style="color:red;">●</span> Destination<br>
        <span style="color:blue;">●</span> Transfer

        <hr>

        <small>
            Solid blue lines: railway geometry<br>
            Solid road lines: OSRM road routes<br>
            Dashed lines: approximate transit routes
        </small>

    </div>
    """

    route_map.get_root().html.add_child(
        folium.Element(legend_html)
    )

    return route_map