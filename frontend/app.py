import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from frontend.common import boot, traffic_inputs

st.set_page_config(page_title="Chennai Smart Travel AI", page_icon="🚆", layout="wide")

st.markdown("""
<style>
.hero {padding: 35px; border-radius: 15px; background: linear-gradient(120deg, #14213d, #1b4965); color: white;}
.hero h1 {font-size: 38px; margin-bottom: 6px;}
.hero p {font-size: 17px; color: #d6e4f0; margin: 0;}
.card {padding: 20px; border-radius: 12px; border: 1px solid rgba(128,128,128,.35); margin-bottom: 14px;}
.card h3 {margin-top: 0;}
</style>
""", unsafe_allow_html=True)

info = boot()

from backend.services import assistant_service, route_service, traffic_service
from ml import predictor

st.sidebar.title("🚆 SmartRoute AI")
st.sidebar.caption("Intelligent mobility platform for Chennai")
st.sidebar.success("System online")
st.sidebar.caption(f"Delay model: {predictor.model_info()['model']} ({predictor.model_info()['source']})")
st.sidebar.caption(assistant_service.llm_status())

st.markdown("""
<div class="hero">
  <h1>Chennai Smart Travel AI</h1>
  <p>Multi-modal route planning across metro, local train, bus, auto, bike taxi and cab, with machine-learning
  traffic prediction, SQL analytics and a tool-using AI assistant.</p>
</div>
""", unsafe_allow_html=True)
st.write("")

places = route_service.list_locations(network_only=True)
c = st.columns(5)
c[0].metric("Places", len(places))
c[1].metric("Route options (SQL)", info["counts"]["transport_routes"])
c[2].metric("Traffic records", f"{info['counts']['traffic_history']:,}")
c[3].metric("Delay model", predictor.model_info()["model"])
c[4].metric("Journeys searched", info["counts"]["journey_logs"])

st.subheader("⚡ Quick plan")
q1, q2, q3 = st.columns([2, 2, 1])
start = q1.selectbox("From", places, index=places.index("Egmore") if "Egmore" in places else 0)
dest = q2.selectbox("To", [p for p in places if p != start], index=0)
priority = q3.selectbox("Priority", ["Fastest", "Cheapest", "Shortest"])
use_traffic = st.checkbox("Include predicted traffic", value=True)
ctx = traffic_inputs("home") if use_traffic else None
if st.button("Plan my journey", type="primary"):
    res = route_service.plan_route(start, dest, priority, traffic=ctx, source="home")
    if not res["ok"]:
        st.error(res["error"])
    else:
        j = res["journey"]
        m = st.columns(3)
        m[0].metric("Time", f"{j['total_minutes']:.0f} min")
        m[1].metric("Fare", f"₹{j['total_fare_inr']:.0f}")
        m[2].metric("Distance", f"{j['total_distance_km']:.1f} km")
        for i, s in enumerate(j["steps"], 1):
            st.write(f"**{i}. {s['from']} → {s['to']}** by {s['transport']}: {s['minutes']:.0f} min, ₹{s['fare_inr']:.0f}")
        st.caption("Prototype estimates, not live fares or live traffic.")

st.subheader("What's inside")
a, b = st.columns(2)
with a:
    st.markdown('<div class="card"><h3>🗺️ Route engine</h3>NetworkX graph over metro, rail, bus, auto, bike and cab. '
                'Fastest / cheapest / shortest, CMRL fares, discounted fares.</div>'
                '<div class="card"><h3>🚦 ML + deep learning</h3>Ridge, Random Forest, Gradient Boosting and a neural network '
                'predict delays from hour, weekday, month and rain. Routes become traffic-aware.</div>'
                '<div class="card"><h3>🗄️ SQL analytics</h3>SQLite schema with views, window functions and usage logs.</div>', unsafe_allow_html=True)
with b:
    st.markdown('<div class="card"><h3>🤖 Generative AI</h3>Tool-calling agent, 4-agent trip planner and a RAG knowledge base '
                '(Groq LLM when a key is set, offline rules otherwise).</div>'
                '<div class="card"><h3>🔌 API + MCP</h3>FastAPI endpoints and an MCP server expose the same tools to other apps.</div>'
                '<div class="card"><h3>🧪 Fine-tuning</h3>LoRA / QLoRA dataset and training script for a small open model.</div>', unsafe_allow_html=True)
st.caption("Use the pages in the sidebar: Route Planner, AI Travel Assistant, Traffic Prediction, Fare Calculator, Analytics, Live Map, Admin.")
