"""Traffic / delay simulation for Chennai.

IMPORTANT: there is no public minute-by-minute Chennai travel-time feed in this project, so the training data is
SIMULATED from the assumptions below (rush-hour peaks, north-east monsoon rain in Oct-Dec, mode sensitivity).
The code, schema and models are real; swap data/processed/traffic_history.csv for real observations
(e.g. exported probe / GPS data) and re-run `python -m ml.training.train_delay_model` to get a real model.

delay_ratio = actual_travel_time / scheduled_travel_time    (1.00 = on time, 1.40 = 40 % slower)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import settings

# sensitivity of each mode to rush hour / rain, and its day-to-day randomness (assumptions, documented in README)
MODE_PARAMS = {
    "Metro":            {"peak": 0.02, "rain": 0.02, "noise": 0.02},
    "Local Train":      {"peak": 0.08, "rain": 0.10, "noise": 0.05},
    "MTC Bus":          {"peak": 0.50, "rain": 0.35, "noise": 0.12},
    "Share Auto":       {"peak": 0.42, "rain": 0.35, "noise": 0.12},
    "Pink Auto":        {"peak": 0.38, "rain": 0.32, "noise": 0.11},
    "Rapido Bike Taxi": {"peak": 0.30, "rain": 0.32, "noise": 0.10},
    "Cab":              {"peak": 0.55, "rain": 0.40, "noise": 0.13},
}
DEFAULT_PARAMS = {"peak": 0.35, "rain": 0.30, "noise": 0.10}

# probability that it rains at some level in a given month (Chennai gets most rain in Oct-Dec)
RAIN_PROB_BY_MONTH = {1: .05, 2: .03, 3: .03, 4: .05, 5: .10, 6: .15, 7: .20, 8: .20, 9: .25, 10: .45, 11: .50, 12: .30}


def _bump(x: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def peak_intensity(hour: float, day_of_week: int) -> float:
    """0..1 congestion pressure at a given hour. Weekdays: 9 am and 6:30 pm peaks. Weekends: gentler midday/evening."""
    if day_of_week >= 5:
        return 0.45 * _bump(hour, 12.5, 3.0) + 0.35 * _bump(hour, 18.0, 2.0)
    return max(_bump(hour, 9.0, 1.4), _bump(hour, 18.5, 1.6))


def expected_ratio(mode: str, hour: float, day_of_week: int, month: int, rain_level: int) -> float:
    """Noise-free delay ratio. Also used as the fallback predictor when no trained model exists."""
    p = MODE_PARAMS.get(mode, DEFAULT_PARAMS)
    peak = peak_intensity(hour, day_of_week)
    rain = {0: 0.0, 1: 0.5, 2: 1.0}[int(rain_level)]
    return 1.0 + p["peak"] * peak + p["rain"] * rain + 0.25 * p["rain"] * rain * peak


def generate_traffic_history(n_rows: int = 30000, seed: int = 42, routes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Simulate n_rows observed journeys on the project's real route table."""
    rng = np.random.default_rng(seed)
    if routes is None:
        routes = pd.read_csv(settings.RAW_DIR / "transport_options.csv")
    routes = routes.drop_duplicates(subset=["start", "destination", "transport_mode"]).reset_index(drop=True)
    pick = rng.integers(0, len(routes), n_rows)
    r = routes.iloc[pick].reset_index(drop=True)

    hour_f = rng.uniform(5, 23.99, n_rows)                       # service hours
    dow = rng.integers(0, 7, n_rows)
    month = rng.integers(1, 13, n_rows)
    rain_p = np.array([RAIN_PROB_BY_MONTH[m] for m in month])
    rainy = rng.random(n_rows) < rain_p
    rain_level = np.where(rainy, np.where(rng.random(n_rows) < 0.7, 1, 2), 0)

    ratios = np.empty(n_rows)
    for i in range(n_rows):
        mode = r.at[i, "transport_mode"]
        base = expected_ratio(mode, hour_f[i], int(dow[i]), int(month[i]), int(rain_level[i]))
        noise = rng.normal(0, MODE_PARAMS.get(mode, DEFAULT_PARAMS)["noise"])
        ratios[i] = max(0.9, base + noise)

    base_time = r["estimated_time_min"].astype(float).to_numpy()
    df = pd.DataFrame({
        "hour": hour_f.astype(int),
        "day_of_week": dow,
        "month": month,
        "rain_level": rain_level,
        "mode": r["transport_mode"].astype(str),
        "distance_km": r["distance_km"].astype(float),
        "base_time_min": base_time,
        "actual_time_min": np.round(base_time * ratios, 2),
        "delay_ratio": np.round(ratios, 4),
    })
    return df


if __name__ == "__main__":
    out = generate_traffic_history()
    out.to_csv(settings.TRAFFIC_CSV, index=False)
    print(f"wrote {len(out)} rows -> {settings.TRAFFIC_CSV}")
