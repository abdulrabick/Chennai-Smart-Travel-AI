import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json

import pandas as pd
import streamlit as st

from frontend.common import boot

st.set_page_config(page_title="Admin", page_icon="⚙️", layout="wide")
info = boot()

import settings
from backend.services import assistant_service
from db import database as dbm
from genai.rag.retriever import get_retriever
from ml import predictor

st.title("⚙️ Admin")
st.caption(assistant_service.llm_status())

st.subheader("Database")
counts = dbm.table_counts()
cols = st.columns(len(counts))
for col, (k, v) in zip(cols, counts.items()):
    col.metric(k.replace("_", " ").title(), f"{v:,}")

st.subheader("Delay model")
st.write(f"Active predictor: **{predictor.model_info()['model']}** ({predictor.model_info()['source']})")
if settings.METRICS_PATH.exists():
    rep = json.loads(settings.METRICS_PATH.read_text(encoding="utf-8"))
    st.dataframe(pd.DataFrame(rep["results"]).T.round(4), use_container_width=True)
    st.markdown("**Feature importance** (permutation, best model)")
    st.bar_chart(pd.Series(rep["feature_importance"]))
c1, c2 = st.columns(2)
if c1.button("🔁 Re-train models"):
    from ml.training.train_delay_model import train
    with st.spinner("Training Ridge, Random Forest, Gradient Boosting and the neural network..."):
        train(verbose=False)
        predictor.reload_model()
    st.success("Models re-trained.")
    st.rerun()
if c2.button("🎲 Re-simulate traffic history + re-train"):
    from ml.traffic_data import generate_traffic_history
    from ml.training.train_delay_model import train
    with st.spinner("Simulating 30,000 journeys and training..."):
        df = generate_traffic_history(30000)
        df.to_csv(settings.TRAFFIC_CSV, index=False)
        dbm.load_traffic_history(df)
        train(df, verbose=False)
        predictor.reload_model()
    st.success("Done.")
    st.rerun()

st.subheader("Knowledge base (RAG)")
if st.button("Rebuild knowledge index"):
    get_retriever(rebuild=True)
    st.success("Rebuilt.")
retr = get_retriever()
src = pd.DataFrame({"source": [d.source for d, _ in retr.chunks]}).value_counts().rename("chunks").reset_index()
st.dataframe(src, use_container_width=True, hide_index=True)
st.caption(f"Add official CMRL / MTC / Southern Railway notes as .md, .txt or .pdf files in {settings.KNOWLEDGE_DIR.name}/ and press Rebuild.")

st.subheader("Recent activity")
t1, t2 = st.tabs(["Journeys", "Assistant chats"])
t1.dataframe(dbm.query_df("SELECT * FROM journey_logs ORDER BY id DESC LIMIT 25"), use_container_width=True, hide_index=True)
t2.dataframe(dbm.query_df("SELECT id, created_at, agent, question, tools_used FROM chat_logs ORDER BY id DESC LIMIT 25"),
             use_container_width=True, hide_index=True)
