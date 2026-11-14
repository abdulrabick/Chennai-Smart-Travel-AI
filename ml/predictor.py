"""Delay prediction used by the route engine, the API, the agent and the Streamlit pages.

Uses the trained model in ml/models/delay_model.joblib. If that file is missing (or cannot be loaded, e.g. a different
scikit-learn version) it falls back to the transparent rule in ml.traffic_data.expected_ratio, so the app never breaks.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from functools import lru_cache

import pandas as pd

import settings
from ml.features import build_features
from ml.traffic_data import MODE_PARAMS, expected_ratio

RAIN_LABELS = {0: "No rain", 1: "Light rain", 2: "Heavy rain"}
DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass(frozen=True)
class TrafficContext:
    """When (and in what weather) the journey happens."""
    hour: int = 9
    day_of_week: int = 0          # 0 = Monday
    month: int = 1
    rain_level: int = 0           # 0 none, 1 light, 2 heavy

    def __post_init__(self):
        if not 0 <= int(self.hour) <= 23:
            raise ValueError("hour must be 0-23")
        if not 0 <= int(self.day_of_week) <= 6:
            raise ValueError("day_of_week must be 0 (Mon) - 6 (Sun)")
        if not 1 <= int(self.month) <= 12:
            raise ValueError("month must be 1-12")
        if int(self.rain_level) not in (0, 1, 2):
            raise ValueError("rain_level must be 0, 1 or 2")

    @classmethod
    def now(cls, rain_level: int = 0) -> "TrafficContext":
        n = datetime.now()
        return cls(n.hour, n.weekday(), n.month, rain_level)

    @classmethod
    def from_dict(cls, d: dict | None):
        if not d:
            return None
        return cls(int(d.get("hour", 9)), int(d.get("day_of_week", 0)), int(d.get("month", 1)), int(d.get("rain_level", 0)))

    def to_dict(self) -> dict:
        return asdict(self)

    def describe(self) -> str:
        return f"{DAY_LABELS[self.day_of_week]} {self.hour:02d}:00, {RAIN_LABELS[self.rain_level].lower()}"


@lru_cache(maxsize=1)
def _load_model():
    path = settings.DELAY_MODEL_PATH
    if not path.exists():
        return None
    try:
        import joblib
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return joblib.load(path)
    except Exception as exc:                       # version mismatch, corrupt file...
        print(f"[ml.predictor] could not load model ({exc}); using rule-based fallback")
        return None


def reload_model() -> None:
    """Call after re-training so the new model is picked up."""
    _load_model.cache_clear()


def model_info() -> dict:
    m = _load_model()
    return {"source": "trained model" if m else "rule-based fallback", "model": m["name"] if m else "expected_ratio()"}


def predict_ratio_df(df: pd.DataFrame) -> pd.Series:
    """df columns: mode, distance_km, base_time_min, hour, day_of_week, month, rain_level -> delay ratios."""
    m = _load_model()
    if m is not None:
        pred = m["pipeline"].predict(build_features(df))
        return pd.Series(pred, index=df.index).clip(lower=0.9)
    vals = [expected_ratio(r.mode, r.hour, r.day_of_week, r.month, r.rain_level) for r in df.itertuples()]
    return pd.Series(vals, index=df.index)


def predict_ratio(mode: str, ctx: TrafficContext, distance_km: float = 8.0, base_time_min: float = 20.0) -> float:
    df = pd.DataFrame([{"mode": mode, "distance_km": distance_km, "base_time_min": base_time_min, "hour": ctx.hour,
                        "day_of_week": ctx.day_of_week, "month": ctx.month, "rain_level": ctx.rain_level}])
    return float(predict_ratio_df(df).iloc[0])


def predict_delay(mode: str, ctx: TrafficContext, distance_km: float = 8.0, base_time_min: float = 20.0) -> dict:
    ratio = predict_ratio(mode, ctx, distance_km, base_time_min)
    expected = base_time_min * ratio
    level = "low" if ratio < 1.10 else "moderate" if ratio < 1.30 else "high"
    return {"mode": mode, "scheduled_minutes": round(base_time_min, 1), "expected_minutes": round(expected, 1),
            "extra_minutes": round(expected - base_time_min, 1), "delay_ratio": round(ratio, 3), "delay_level": level,
            "when": ctx.describe(), "predictor": model_info()["source"]}


def snapshot_all_modes(ctx: TrafficContext, distance_km: float = 8.0, base_time_min: float = 20.0) -> pd.DataFrame:
    rows = [predict_delay(m, ctx, distance_km, base_time_min) for m in MODE_PARAMS]
    return pd.DataFrame(rows).sort_values("delay_ratio").reset_index(drop=True)


def hourly_curve(mode: str, day_of_week: int, month: int, rain_level: int, distance_km: float = 8.0,
                 base_time_min: float = 20.0, hours=range(5, 24)) -> pd.DataFrame:
    df = pd.DataFrame([{"mode": mode, "distance_km": distance_km, "base_time_min": base_time_min, "hour": h,
                        "day_of_week": day_of_week, "month": month, "rain_level": rain_level} for h in hours])
    df["delay_ratio"] = predict_ratio_df(df).round(3)
    df["expected_minutes"] = (df["base_time_min"] * df["delay_ratio"]).round(1)
    return df[["hour", "delay_ratio", "expected_minutes"]]


def adjust_graph_times(graph, ctx: TrafficContext | None):
    """Return a COPY of a NetworkX transport graph whose edge 'time' values reflect predicted traffic at ctx.
    The scheduled time is kept in edge['base_time'] and the multiplier in edge['delay_ratio']."""
    if ctx is None:
        return graph
    g = graph.copy()
    edges, rows = [], []
    for u, v, key, data in g.edges(keys=True, data=True):
        edges.append((u, v, key))
        rows.append({"mode": data["transport_mode"], "distance_km": float(data.get("distance", 1.0)),
                     "base_time_min": float(data["time"]), "hour": ctx.hour, "day_of_week": ctx.day_of_week,
                     "month": ctx.month, "rain_level": ctx.rain_level})
    if not rows:
        return g
    ratios = predict_ratio_df(pd.DataFrame(rows)).tolist()
    for (u, v, key), ratio in zip(edges, ratios):
        d = g[u][v][key]
        d["base_time"] = d["time"]
        d["delay_ratio"] = float(ratio)
        d["time"] = round(d["time"] * float(ratio), 2)
    return g
