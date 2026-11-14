"""Traffic / delay prediction service."""
from __future__ import annotations

import pandas as pd

from backend.services import route_service
from ml import predictor
from ml.predictor import TrafficContext


def predict_delay(mode: str, hour: int, day_of_week: int = 0, month: int = 1, rain_level: int = 0,
                  distance_km: float = 8.0, base_time_min: float = 20.0) -> dict:
    ctx = TrafficContext(hour, day_of_week, month, rain_level)
    return predictor.predict_delay(mode, ctx, distance_km, base_time_min)


def best_departure(start: str, destination: str, day_of_week: int = 0, month: int = 1, rain_level: int = 0,
                   priority: str = "Fastest", mode: str | None = None, hours=range(5, 23)) -> dict:
    """Try every departure hour with the traffic-aware router and report the fastest and slowest."""
    rows = []
    for h in hours:
        res = route_service.plan_route(start, destination, priority, "regular", mode,
                                       TrafficContext(h, day_of_week, month, rain_level), log=False)
        if not res["ok"]:
            return res
        j = res["journey"]
        rows.append({"hour": h, "minutes": j["total_minutes"], "fare_inr": j["total_fare_inr"],
                     "transport": " + ".join(j["transport_used"])})
    df = pd.DataFrame(rows)
    best, worst = df.loc[df["minutes"].idxmin()], df.loc[df["minutes"].idxmax()]
    return {"ok": True, "start": res["journey"]["start"], "destination": res["journey"]["destination"],
            "best_hour": int(best["hour"]), "best_minutes": float(best["minutes"]),
            "worst_hour": int(worst["hour"]), "worst_minutes": float(worst["minutes"]),
            "minutes_saved": round(float(worst["minutes"] - best["minutes"]), 1),
            "when": TrafficContext(0, day_of_week, month, rain_level).describe().split(" ", 2)[0] + ", " +
                    predictor.RAIN_LABELS[rain_level].lower(),
            "by_hour": df.to_dict("records")}


def traffic_impact(start: str, destination: str, ctx: TrafficContext, priority: str = "Fastest", mode: str | None = None) -> dict:
    """Same trip with and without predicted traffic, to show what the ML model changes."""
    free = route_service.plan_route(start, destination, priority, "regular", mode, None, log=False)
    busy = route_service.plan_route(start, destination, priority, "regular", mode, ctx, log=False)
    if not (free["ok"] and busy["ok"]):
        return free if not free["ok"] else busy
    a, b = free["journey"], busy["journey"]
    return {"ok": True, "scheduled": a, "with_traffic": b, "extra_minutes": round(b["total_minutes"] - a["total_minutes"], 1),
            "route_changed": a["route"] != b["route"] or a["transport_used"] != b["transport_used"]}


def modes_snapshot(ctx: TrafficContext, distance_km: float = 8.0, base_time_min: float = 20.0) -> pd.DataFrame:
    return predictor.snapshot_all_modes(ctx, distance_km, base_time_min)
