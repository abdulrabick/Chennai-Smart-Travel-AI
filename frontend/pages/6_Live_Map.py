import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import folium
import streamlit as st
from streamlit_folium import st_folium

from frontend.common import boot, traffic_inputs

st.set_page_config(page_title="Live Map", page_icon="🌍", layout="wide")
boot()

from backend.services import route_service
from db.database import query_df
from ml import predictor
from ml.traffic_data import MODE_PARAMS
from transport_engine import find_best_route

st.title("🌍 Chennai Transport Map")
st.caption("Connections are coloured by the delay the ML model predicts for the chosen time and weather "
           "(simulated, not live traffic).")

ctx = traffic_inputs("map")
mode = st.selectbox("Transport mode", list(MODE_PARAMS), index=2)

locs = query_df("SELECT name, latitude, longitude FROM locations").set_index("name")
routes = query_df("SELECT * FROM transport_routes WHERE transport_mode = ?", (mode,))

fmap = folium.Map(location=[13.04, 80.22], zoom_start=11, tiles="OpenStreetMap", control_scale=True)
for name, r in locs.iterrows():
    folium.CircleMarker([r.latitude, r.longitude], radius=5, color="#14213d", fill=True, fill_opacity=0.9, tooltip=name).add_to(fmap)
for r in routes.itertuples():
    if r.start not in locs.index or r.destination not in locs.index:
        continue
    ratio = predictor.predict_ratio(mode, ctx, r.distance_km, r.estimated_time_min)
    color = "#d62828" if ratio >= 1.30 else "#f77f00" if ratio >= 1.10 else "#2a9d8f"
    folium.PolyLine([[locs.loc[r.start, "latitude"], locs.loc[r.start, "longitude"]],
                     [locs.loc[r.destination, "latitude"], locs.loc[r.destination, "longitude"]]],
                    color=color, weight=6, opacity=0.85,
                    tooltip=f"{r.start} ↔ {r.destination}: {r.estimated_time_min:.0f} min scheduled, "
                            f"{r.estimated_time_min * ratio:.0f} min expected ({ratio:.2f}x)").add_to(fmap)
st_folium(fmap, height=480, use_container_width=True, returned_objects=[])
st.caption("🟢 on time (<1.10x)   🟠 slower (1.10-1.30x)   🔴 heavily delayed (>1.30x)")

st.subheader("Journey on the map")
places = route_service.list_locations(network_only=True)
a, b, c = st.columns([2, 2, 1])
start = a.selectbox("From", places, index=places.index("Egmore") if "Egmore" in places else 0, key="lm_from")
dest = b.selectbox("To", [p for p in places if p != start], index=0, key="lm_to")
prio = c.selectbox("Priority", ["Fastest", "Cheapest", "Shortest"], key="lm_prio")
if st.button("Show route on map", type="primary"):
    result = find_best_route(start, dest, prio, "regular", None, traffic=ctx)
    if result is None:
        st.warning("No route found.")
    else:
        st.write(f"**{result['total_time']:.0f} min · ₹{result['total_fare']:.0f} · {result['total_distance']:.1f} km** "
                 f"({ctx.describe()})")
        try:
            from map_engine import create_route_map
            st_folium(create_route_map(result["route"], result["steps"]), height=480, use_container_width=True, returned_objects=[])
        except Exception as exc:        # road drawing needs internet (OSRM)
            st.error(f"Could not draw the detailed map: {exc}")
