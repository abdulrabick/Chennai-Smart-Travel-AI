"""Feature engineering shared by training and prediction."""
from __future__ import annotations

import numpy as np
import pandas as pd

NUMERIC_FEATURES = ["distance_km", "base_time_min", "hour_sin", "hour_cos", "day_of_week",
                    "is_weekend", "month_sin", "month_cos", "rain_level", "is_peak"]
CATEGORICAL_FEATURES = ["mode"]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw columns (mode, distance_km, base_time_min, hour, day_of_week, month, rain_level) into model inputs.
    Hour and month are encoded as sin/cos so 23:00 is close to 00:00 and December is close to January."""
    out = pd.DataFrame(index=df.index)
    out["mode"] = df["mode"].astype(str)
    out["distance_km"] = df["distance_km"].astype(float)
    out["base_time_min"] = df["base_time_min"].astype(float)
    out["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    out["day_of_week"] = df["day_of_week"].astype(int)
    out["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    out["month_sin"] = np.sin(2 * np.pi * (df["month"] - 1) / 12)
    out["month_cos"] = np.cos(2 * np.pi * (df["month"] - 1) / 12)
    out["rain_level"] = df["rain_level"].astype(int)
    peak_hours = df["hour"].isin([8, 9, 10, 17, 18, 19, 20]) & (df["day_of_week"] < 5)
    out["is_peak"] = peak_hours.astype(int)
    return out[ALL_FEATURES]
