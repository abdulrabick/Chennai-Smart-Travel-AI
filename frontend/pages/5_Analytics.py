import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from frontend.common import boot

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")
boot()

from backend.services import analytics_service as an

st.title("📊 Transport Analytics")
st.caption("Every chart below is produced by a SQL query (GROUP BY, views, window functions, CTEs) over the SQLite database.")

counts = an.overview()
cols = st.columns(len(counts))
for col, (k, v) in zip(cols, counts.items()):
    col.metric(k.replace("_", " ").title(), f"{v:,}")

t1, t2, t3, t4, t5 = st.tabs(["Modes", "Delay patterns", "Reliability", "Rankings", "Usage"])

with t1:
    ms = an.mode_summary()
    st.dataframe(ms, use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.bar_chart(ms.set_index("transport_mode")["fare_per_km"], y_label="₹ per km")
    c2.bar_chart(ms.set_index("transport_mode")["avg_speed_kmph"], y_label="Average speed (km/h)")

with t2:
    st.markdown("**Average delay ratio by hour** (1.30 = 30 % slower than schedule)")
    st.line_chart(an.delay_by_hour().pivot(index="hour", columns="mode", values="avg_delay_ratio"))
    c1, c2 = st.columns(2)
    rain = an.delay_by_rain()
    c1.markdown("**Effect of rain**")
    c1.bar_chart(rain.pivot(index="mode", columns="rain", values="avg_delay_ratio")[["No rain", "Light rain", "Heavy rain"]])
    c2.markdown("**Rush hour vs off-peak (weekdays)**")
    c2.dataframe(an.peak_vs_offpeak(), use_container_width=True, hide_index=True)

with t3:
    rel = an.reliability_by_mode()
    st.dataframe(rel, use_container_width=True, hide_index=True)
    st.bar_chart(rel.set_index("mode")["pct_trips_over_25pct_late"], y_label="% of trips >25 % late")

with t4:
    st.markdown("**Which mode wins most often?**")
    st.dataframe(an.best_value_modes(), use_container_width=True, hide_index=True)
    st.markdown("**Rank of every mode on every route** (window functions)")
    st.dataframe(an.mode_rankings(), use_container_width=True, hide_index=True)

with t5:
    pop = an.popular_routes()
    if pop.empty:
        st.info("No journeys logged yet. Plan a few routes and come back.")
    else:
        st.dataframe(pop, use_container_width=True, hide_index=True)
        days = an.searches_by_day()
        if len(days):
            st.line_chart(days.set_index("day")["searches"])
    fb = an.feedback_summary()
    if len(fb):
        st.markdown("**Feedback by route type**")
        st.dataframe(fb, use_container_width=True, hide_index=True)
