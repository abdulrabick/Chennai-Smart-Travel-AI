"""The tools the agents can call. One registry feeds: the Groq agent (JSON schemas), the offline agent (direct calls),
the multi-agent pipeline and the MCP server, so behaviour is identical everywhere."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.services import route_service, traffic_service
from genai.rag.retriever import get_retriever
from ml.predictor import TrafficContext
from ml.traffic_data import MODE_PARAMS

MODES = list(MODE_PARAMS)


def make_context(hour=None, day_of_week=None, month=None, rain_level=0) -> TrafficContext | None:
    """No hour -> no traffic adjustment. Missing day/month default to today's."""
    if hour is None:
        return None
    now = TrafficContext.now()
    return TrafficContext(int(hour), now.day_of_week if day_of_week is None else int(day_of_week),
                          now.month if month is None else int(month), int(rain_level or 0))


def plan_journey(start: str, destination: str, priority: str = "Fastest", fare_type: str = "regular", mode: str | None = None,
                 hour: int | None = None, day_of_week: int | None = None, month: int | None = None, rain_level: int = 0) -> dict:
    return route_service.plan_route(start, destination, priority, fare_type, mode,
                                    make_context(hour, day_of_week, month, rain_level), source="agent")


def plan_within_budget(start: str, destination: str, budget: float, fare_type: str = "regular") -> dict:
    return route_service.plan_within_budget(start, destination, float(budget), fare_type)


def compare_transport_modes(start: str, destination: str) -> dict:
    df = route_service.direct_options(start, destination)
    return {"ok": True, "start": start, "destination": destination, "options": df.to_dict("records")}


def predict_delay(mode: str, hour: int, day_of_week: int = 0, month: int = 1, rain_level: int = 0) -> dict:
    return {"ok": True, **traffic_service.predict_delay(mode, int(hour), int(day_of_week), int(month), int(rain_level))}


def best_departure_time(start: str, destination: str, day_of_week: int = 0, month: int | None = None, rain_level: int = 0) -> dict:
    month = TrafficContext.now().month if month is None else int(month)
    res = traffic_service.best_departure(start, destination, int(day_of_week), month, int(rain_level))
    res.pop("by_hour", None)               # keep tool output short for the LLM
    return res


def metro_fare(start: str, destination: str, fare_type: str = "regular") -> dict:
    return route_service.metro_fare(start, destination, fare_type)


def search_knowledge(query: str) -> dict:
    return {"ok": True, "passages": [p.to_dict() for p in get_retriever().search(query, k=3)]}


def list_places() -> dict:
    return {"ok": True, "places": route_service.list_locations(network_only=True)}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


_S = {"type": "string"}
_PLACE = {"type": "string", "description": "A place name from list_places, e.g. Guindy or Chennai Central"}
_TRAFFIC = {
    "hour": {"type": "integer", "description": "Departure hour 0-23. Omit to ignore traffic."},
    "day_of_week": {"type": "integer", "description": "0=Monday ... 6=Sunday"},
    "month": {"type": "integer", "description": "1-12"},
    "rain_level": {"type": "integer", "description": "0 none, 1 light, 2 heavy"},
}

TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("plan_journey", "Find the best multi-modal journey (metro, local train, bus, auto, bike taxi, cab) between two places. "
         "Pass hour/day/rain to include predicted traffic delays.",
         _obj({"start": _PLACE, "destination": _PLACE, "priority": {"type": "string", "enum": ["Fastest", "Cheapest", "Shortest"]},
               "fare_type": {"type": "string", "enum": ["regular", "discounted"]}, "mode": {"type": "string", "enum": MODES}, **_TRAFFIC},
              ["start", "destination"]), plan_journey),
    Tool("plan_within_budget", "Find the cheapest journey and check it fits a rupee budget.",
         _obj({"start": _PLACE, "destination": _PLACE, "budget": {"type": "number"}}, ["start", "destination", "budget"]), plan_within_budget),
    Tool("compare_transport_modes", "List every direct transport option between two places with fare, time and distance.",
         _obj({"start": _PLACE, "destination": _PLACE}, ["start", "destination"]), compare_transport_modes),
    Tool("predict_delay", "Predict how much slower than scheduled a transport mode will be at a given time and weather.",
         _obj({"mode": {"type": "string", "enum": MODES}, "hour": {"type": "integer"}, "day_of_week": {"type": "integer"},
               "month": {"type": "integer"}, "rain_level": {"type": "integer"}}, ["mode", "hour"]), predict_delay),
    Tool("best_departure_time", "Find the best hour to leave to minimise travel time between two places.",
         _obj({"start": _PLACE, "destination": _PLACE, "day_of_week": {"type": "integer"}, "month": {"type": "integer"},
               "rain_level": {"type": "integer"}}, ["start", "destination"]), best_departure_time),
    Tool("metro_fare", "Chennai Metro fare, stops and lines between two metro stations.",
         _obj({"start": _S, "destination": _S, "fare_type": {"type": "string", "enum": ["regular", "discounted"]}}, ["start", "destination"]), metro_fare),
    Tool("search_knowledge", "Search the Chennai transport knowledge base (metro network, fare slabs, mode comparison, how the system works).",
         _obj({"query": _S}, ["query"]), search_knowledge),
    Tool("list_places", "List the places the journey planner knows.", _obj({}, []), list_places),
]}


def openai_tool_specs() -> list[dict]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in TOOLS.values()]


def call_tool(name: str, arguments: dict | None) -> dict:
    """Run a tool safely. Errors are returned as data so the LLM (or UI) can react to them."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"ok": False, "error": f"Unknown tool '{name}'."}
    allowed = set(tool.parameters["properties"])
    args = {k: v for k, v in (arguments or {}).items() if k in allowed and v is not None}
    try:
        return tool.fn(**args)
    except TypeError as exc:
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"{name} failed: {exc}"}
