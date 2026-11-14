"""Route planning service: wraps transport_engine with validation, JSON-safe output and usage logging."""
from __future__ import annotations

import difflib
from functools import lru_cache

import pandas as pd

from db import database as dbm
from ml.predictor import TrafficContext
from transport_engine import build_transport_graph, compare_routes, find_best_route, find_route_within_budget

PRIORITIES = ("Fastest", "Cheapest", "Shortest")


@lru_cache(maxsize=1)
def _all_locations() -> tuple[str, ...]:
    return tuple(sorted(build_transport_graph().nodes()))


def list_locations(network_only: bool = False) -> list[str]:
    """network_only=True -> only the places in the route dataset (no individual metro stations)."""
    if network_only:
        df = dbm.query_df("SELECT start AS p FROM transport_routes UNION SELECT destination FROM transport_routes ORDER BY 1")
        return df["p"].tolist()
    return list(_all_locations())


def resolve_location(name: str, cutoff: float = 0.78) -> str | None:
    """Match user text to a known place: exact, case-insensitive, then close spelling."""
    if not name:
        return None
    places = _all_locations()
    folded = {p.casefold(): p for p in places}
    key = name.strip().casefold()
    if key in folded:
        return folded[key]
    close = difflib.get_close_matches(key, list(folded), n=1, cutoff=cutoff)
    return folded[close[0]] if close else None


def summarize_journey(result: dict | None) -> dict | None:
    if result is None:
        return None
    steps = []
    for s in result["steps"]:
        item = {"from": s["from"], "to": s["to"], "transport": s["transport"], "minutes": round(float(s["time"]), 1),
                "fare_inr": round(float(s["fare"]), 1), "distance_km": round(float(s["distance"]), 1)}
        if s.get("lines"):
            item["metro_lines"] = s["lines"]
            item["stops"] = max(len(s.get("stations", [])) - 1, 0)
        steps.append(item)
    return {"route": result["route"], "steps": steps, "total_minutes": round(float(result["total_time"]), 1),
            "total_fare_inr": round(float(result["total_fare"]), 1), "total_distance_km": round(float(result["total_distance"]), 1),
            "transport_used": list(dict.fromkeys(s["transport"] for s in result["steps"])),
            "traffic": result.get("traffic")}


def plan_route(start: str, destination: str, priority: str = "Fastest", fare_type: str = "regular", mode: str | None = None,
               traffic: TrafficContext | dict | None = None, log: bool = True, source: str = "app") -> dict:
    """Return {'ok': True, 'journey': {...}} or {'ok': False, 'error': '...'}."""
    if isinstance(traffic, dict):
        traffic = TrafficContext.from_dict(traffic)
    s, d = resolve_location(start), resolve_location(destination)
    if not s:
        return {"ok": False, "error": f"Unknown starting place '{start}'. Try one of: {', '.join(list_locations(True))}."}
    if not d:
        return {"ok": False, "error": f"Unknown destination '{destination}'. Try one of: {', '.join(list_locations(True))}."}
    if s == d:
        return {"ok": False, "error": "Start and destination are the same place."}
    if priority not in PRIORITIES:
        return {"ok": False, "error": f"priority must be one of {PRIORITIES}."}
    mode = None if mode in (None, "", "All") else mode
    result = find_best_route(s, d, priority, fare_type, mode, traffic=traffic)
    if result is None:
        return {"ok": False, "error": f"No route found between {s} and {d}" + (f" using {mode}." if mode else ".")}
    journey = summarize_journey(result)
    journey.update({"start": s, "destination": d, "priority": priority, "fare_type": fare_type})
    if log:
        try:
            journey["log_id"] = dbm.log_journey(s, d, priority, mode, journey["total_minutes"], journey["total_fare_inr"],
                                                journey["total_distance_km"], traffic is not None, source)
        except Exception as exc:          # logging must never break routing
            print(f"[route_service] could not log journey: {exc}")
    return {"ok": True, "journey": journey}


def compare_priorities(start: str, destination: str, fare_type: str = "regular", mode: str | None = None,
                       traffic: TrafficContext | dict | None = None) -> dict:
    if isinstance(traffic, dict):
        traffic = TrafficContext.from_dict(traffic)
    s, d = resolve_location(start), resolve_location(destination)
    if not s or not d:
        return {"ok": False, "error": "Unknown start or destination."}
    mode = None if mode in (None, "", "All") else mode
    results = compare_routes(s, d, fare_type, mode, traffic=traffic)
    return {"ok": True, "start": s, "destination": d,
            "journeys": {p: summarize_journey(r) for p, r in results.items()}}


def plan_within_budget(start: str, destination: str, budget: float, fare_type: str = "regular",
                       traffic: TrafficContext | dict | None = None) -> dict:
    if isinstance(traffic, dict):
        traffic = TrafficContext.from_dict(traffic)
    s, d = resolve_location(start), resolve_location(destination)
    if not s or not d:
        return {"ok": False, "error": "Unknown start or destination."}
    r = find_route_within_budget(s, d, budget, fare_type, traffic=traffic)
    if r is None:
        return {"ok": False, "error": f"No route between {s} and {d} costs Rs.{budget:.0f} or less."}
    j = summarize_journey(r); j.update({"start": s, "destination": d, "priority": "Cheapest", "budget": budget,
                                         "remaining_budget_inr": round(budget - j["total_fare_inr"], 1)})
    return {"ok": True, "journey": j}


def direct_options(start: str, destination: str) -> pd.DataFrame:
    """All direct (non-metro-network) options between two places, read with SQL in both directions."""
    s, d = resolve_location(start) or start, resolve_location(destination) or destination
    return dbm.query_df(
        """SELECT transport_mode AS mode, distance_km, estimated_time_min AS minutes, estimated_fare_inr AS fare_inr,
                  ROUND(estimated_fare_inr / NULLIF(distance_km, 0), 2) AS fare_per_km
           FROM transport_routes
           WHERE (start = ? AND destination = ?) OR (start = ? AND destination = ?)
           ORDER BY estimated_fare_inr""", (s, d, d, s))


def metro_fare(start: str, destination: str, fare_type: str = "regular") -> dict:
    from metro_engine import get_metro_fare, find_metro_route
    s, d = resolve_location(start), resolve_location(destination)
    if not s or not d:
        return {"ok": False, "error": "Unknown metro station name."}
    try:
        fare = get_metro_fare(s, d, fare_type)
        route = find_metro_route(s, d, "Fastest", fare_type)
    except Exception as exc:
        return {"ok": False, "error": f"No metro fare for {s} to {d}: {exc}"}
    return {"ok": True, "start": s, "destination": d, "fare_inr": fare, "fare_type": fare_type,
            "stops": route["total_stops"], "estimated_minutes": route["estimated_minutes"], "lines": route["lines"]}
