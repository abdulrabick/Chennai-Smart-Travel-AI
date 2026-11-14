import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from frontend.common import boot

st.set_page_config(page_title="Fare Calculator", page_icon="💰", layout="wide")
boot()

from backend.services import route_service

st.title("💰 Fare Calculator")
st.caption("Compares every transport option between two places. Fares are dataset estimates, not live prices.")

all_places = route_service.list_locations()
net = route_service.list_locations(network_only=True)
a, b, c = st.columns([2, 2, 1])
start = a.selectbox("From", all_places, index=all_places.index("Egmore") if "Egmore" in all_places else 0)
dest = b.selectbox("To", [p for p in all_places if p != start], index=0)
fare_type = c.radio("Metro fare", ["regular", "discounted"], format_func=lambda x: "20% discounted" if x == "discounted" else "Regular")

st.subheader("Direct options (SQL)")
opts = route_service.direct_options(start, dest)
if opts.empty:
    st.info("No direct non-metro option between these two places in the dataset. See the journey below.")
else:
    st.dataframe(opts.rename(columns={"mode": "Mode", "distance_km": "Distance (km)", "minutes": "Time (min)",
                                       "fare_inr": "Fare (₹)", "fare_per_km": "₹ per km"}), use_container_width=True, hide_index=True)
    st.bar_chart(opts.set_index("mode")["fare_inr"], y_label="Fare (₹)")

st.subheader("Metro fare")
mf = route_service.metro_fare(start, dest, fare_type)
if mf["ok"]:
    m = st.columns(4)
    m[0].metric("Fare", f"₹{mf['fare_inr']:.0f}")
    m[1].metric("Stops", mf["stops"])
    m[2].metric("Estimated time", f"{mf['estimated_minutes']} min")
    m[3].metric("Line(s)", ", ".join(mf["lines"]))
else:
    st.caption("Both places must be CMRL metro stations for a metro fare.")

st.subheader("Best journeys")
budget = st.slider("Budget (₹)", 10, 500, 100, 10)
cols = st.columns(3)
for col, prio in zip(cols, ("Fastest", "Cheapest", "Shortest")):
    res = route_service.plan_route(start, dest, prio, fare_type, log=False)
    with col, st.container(border=True):
        st.markdown(f"**{prio}**")
        if not res["ok"]:
            st.warning(res["error"])
            continue
        j = res["journey"]
        st.metric("Fare", f"₹{j['total_fare_inr']:.0f}", "within budget" if j["total_fare_inr"] <= budget else "over budget",
                  delta_color="normal" if j["total_fare_inr"] <= budget else "inverse")
        st.write(f"{j['total_minutes']:.0f} min · {j['total_distance_km']:.1f} km")
        st.caption(" → ".join(j["route"]) if len(j["route"]) <= 6 else f"{j['route'][0]} → ... → {j['route'][-1]} ({len(j['route'])} stops)")
