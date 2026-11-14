"""Shared Streamlit helpers (imported by app.py and every page)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
RAIN = {"No rain": 0, "Light rain": 1, "Heavy rain": 2}


@st.cache_resource(show_spinner="Preparing database and training the delay model (first run only, ~15 s)...")
def boot():
    """Create the database, simulate traffic history and train the models if they do not exist yet."""
    from backend.services.bootstrap import ensure_ready
    return ensure_ready(train_if_missing=True)


def traffic_inputs(key: str = "t", sidebar: bool = False):
    """Day / hour / month / rain widgets -> ml.predictor.TrafficContext."""
    from ml.predictor import TrafficContext
    from datetime import datetime
    now = datetime.now()
    box = st.sidebar if sidebar else st
    c1, c2, c3, c4 = (box.columns(4) if not sidebar else (box, box, box, box))
    day = c1.selectbox("Day", DAYS, index=now.weekday(), key=f"{key}_day")
    hour = c2.slider("Departure hour", 0, 23, 9, key=f"{key}_hour")
    month = c3.selectbox("Month", MONTHS, index=now.month - 1, key=f"{key}_month")
    rain = c4.radio("Weather", list(RAIN), key=f"{key}_rain", horizontal=not sidebar)
    return TrafficContext(hour, DAYS.index(day), MONTHS.index(month) + 1, RAIN[rain])
