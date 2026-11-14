import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import pandas as pd
import streamlit as st

from frontend.common import boot, traffic_inputs

st.set_page_config(page_title="Traffic Prediction", page_icon="🚦", layout="wide")
boot()

import settings
from backend.services import route_service, traffic_service
from ml import predictor
from ml.traffic_data import MODE_PARAMS

st.title("🚦 Traffic & Delay Prediction")
st.caption(f"Predictor: {predictor.model_info()['model']} ({predictor.model_info()['source']}). "
           "Trained on simulated Chennai traffic history; see the Admin page for metrics.")

ctx = traffic_inputs("tp")
st.info(f"Scenario: **{ctx.describe()}**")

st.subheader("1. How much slower is each transport mode?")
c1, c2 = st.columns(2)
dist = c1.number_input("Trip distance (km)", 1.0, 60.0, 8.0, 0.5)
base = c2.number_input("Scheduled time (min)", 5.0, 180.0, 20.0, 1.0)
snap = traffic_service.modes_snapshot(ctx, dist, base)
st.dataframe(snap[["mode", "scheduled_minutes", "expected_minutes", "extra_minutes", "delay_ratio", "delay_level"]],
             use_container_width=True, hide_index=True)
st.bar_chart(snap.set_index("mode")["extra_minutes"], y_label="Extra minutes vs schedule")

st.subheader("2. Delay through the day")
mode = st.selectbox("Mode", list(MODE_PARAMS), index=2)
curve = predictor.hourly_curve(mode, ctx.day_of_week, ctx.month, ctx.rain_level, dist, base)
st.line_chart(curve.set_index("hour")["expected_minutes"], y_label="Expected minutes")

st.subheader("3. Traffic-aware journey")
places = route_service.list_locations(network_only=True)
a, b, p = st.columns([2, 2, 1])
start = a.selectbox("From", places, index=places.index("Egmore") if "Egmore" in places else 0, key="tp_from")
dest = b.selectbox("To", [x for x in places if x != start], index=len([x for x in places if x != start]) - 1, key="tp_to")
prio = p.selectbox("Priority", ["Fastest", "Cheapest", "Shortest"], key="tp_prio")
impact = traffic_service.traffic_impact(start, dest, ctx, prio)
if not impact["ok"]:
    st.error(impact["error"])
else:
    m = st.columns(3)
    m[0].metric("Scheduled", f"{impact['scheduled']['total_minutes']:.0f} min")
    m[1].metric("With predicted traffic", f"{impact['with_traffic']['total_minutes']:.0f} min", f"+{impact['extra_minutes']:.0f} min", delta_color="inverse")
    m[2].metric("Fare", f"₹{impact['with_traffic']['total_fare_inr']:.0f}")
    if impact["route_changed"]:
        st.warning("Traffic changes the best option: " + " → ".join(impact["with_traffic"]["route"]))
    else:
        st.success("The best route stays the same: " + " → ".join(impact["with_traffic"]["route"]))

if st.button("⏰ When should I leave?"):
    with st.spinner("Trying every departure hour..."):
        best = traffic_service.best_departure(start, dest, ctx.day_of_week, ctx.month, ctx.rain_level, prio)
    if not best["ok"]:
        st.error(best["error"])
    else:
        st.success(f"Leave around **{best['best_hour']:02d}:00** ({best['best_minutes']:.0f} min). "
                   f"Worst hour is {best['worst_hour']:02d}:00 ({best['worst_minutes']:.0f} min). Saves about {best['minutes_saved']:.0f} min.")
        st.bar_chart(pd.DataFrame(best["by_hour"]).set_index("hour")["minutes"], y_label="Journey minutes")

with st.expander("Model performance"):
    if settings.METRICS_PATH.exists():
        rep = json.loads(settings.METRICS_PATH.read_text(encoding="utf-8"))
        st.write(f"Best model: **{rep['best_model']}**  |  trained on {rep['train_rows']:,} rows, tested on {rep['test_rows']:,}")
        st.dataframe(pd.DataFrame(rep["results"]).T.round(4), use_container_width=True)
        st.caption("Data is simulated (see ml/traffic_data.py). Replace data/processed/traffic_history.csv with real observations to retrain.")
    else:
        st.info("No metrics yet. Open the Admin page and press Train.")
