"""Tool-calling travel agent.

Online  (GROQ_API_KEY set): the LLM decides which tools to call (plan_journey, predict_delay, search_knowledge ...),
                            reads their JSON results and writes the final answer. It may only use tool data for numbers.
Offline (no key / API error): a deterministic router extracts places, time, rain and budget from the question,
                            calls the same tools and formats the answer, so the feature always works.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from backend.services import route_service
from genai.agents import formatting as fmt
from genai.agents.tools import MODES, call_tool, openai_tool_specs

SYSTEM_PROMPT = (
    "You are Chennai Smart Travel AI, a transport assistant for Chennai. "
    "ALWAYS use the provided tools to get routes, fares, times, delays and facts; never invent them. "
    "Quote numbers exactly as the tools return them. Say clearly that figures are prototype estimates, not live data. "
    "If a place is unknown, call list_places and suggest close matches. Keep answers short, friendly and in simple English."
)

MODE_WORDS = {"metro": "Metro", "train": "Local Train", "local": "Local Train", "bus": "MTC Bus", "mtc": "MTC Bus",
              "share auto": "Share Auto", "pink auto": "Pink Auto", "bike": "Rapido Bike Taxi", "rapido": "Rapido Bike Taxi",
              "cab": "Cab", "taxi": "Cab", "uber": "Cab", "ola": "Cab"}
DAY_WORDS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6, "weekend": 5}
PART_OF_DAY = {"morning": 9, "peak": 9, "afternoon": 14, "evening": 18, "night": 21, "midnight": 23}


@dataclass
class AgentResult:
    answer: str
    steps: list[dict] = field(default_factory=list)      # [{"tool":..., "arguments":..., "result":...}]
    used_llm: bool = False
    error: str | None = None


# ------------------------------------------------------------------ request parsing (offline mode + multi-agent planner)
def parse_request(question: str) -> dict:
    q = question.lower()
    places = _find_places(question)
    hour = None
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", q)
    if m:
        hour = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
    else:
        for word, h in PART_OF_DAY.items():
            if word in q:
                hour = h
                break
    day = next((d for w, d in DAY_WORDS.items() if w in q), None)
    rain = 2 if re.search(r"heavy rain|downpour|cyclone|flood", q) else 1 if re.search(r"rain|monsoon|wet|drizzle", q) else 0
    budget = None
    b = re.search(r"(?:budget|under|below|within|less than|max(?:imum)?)\s*(?:is\s*)?(?:of\s*)?(?:₹|rs\.?|inr)?\s*(\d+)", q)
    if b:
        budget = float(b.group(1))
    mode = next((v for k, v in sorted(MODE_WORDS.items(), key=lambda kv: -len(kv[0])) if re.search(rf"\b{k}\b", q)), None)
    priority = "Cheapest" if re.search(r"cheap|lowest fare|least expensive|save money", q) else \
               "Shortest" if re.search(r"shortest|least distance", q) else "Fastest"
    return {"places": places, "hour": hour, "day_of_week": day, "rain_level": rain, "budget": budget, "mode": mode,
            "priority": priority, "text": q}


def _find_places(question: str) -> list[str]:
    """Known place names mentioned in the text, in order of appearance ('from X to Y' wins when present)."""
    m = re.search(r"from\s+(.+?)\s+to\s+(.+?)(?:\s+(?:at|by|on|in|with|using|under|within|budget|during|when|if|for|via)\b|[?.!,]|$)",
                  question, re.I)
    if m:
        a, b = route_service.resolve_location(m.group(1)), route_service.resolve_location(m.group(2))
        if a and b:
            return [a, b]
    found = []
    low = question.casefold()
    for name in sorted(route_service.list_locations(), key=len, reverse=True):
        idx = low.find(name.casefold())
        if idx >= 0 and not any(idx < e and idx + len(name) > s for _, s, e in found):
            found.append((name, idx, idx + len(name)))
    return [n for n, _, _ in sorted(found, key=lambda t: t[1])]


# ------------------------------------------------------------------ the agent
class SmartTravelAgent:
    def __init__(self, llm=None, max_iterations: int = 5):
        self.llm = llm
        self.max_iterations = max_iterations

    def run(self, question: str, history: list[dict] | None = None) -> AgentResult:
        if not question or not question.strip():
            return AgentResult("Please ask a travel question, for example: best way from Egmore to Tambaram at 9 am in heavy rain.")
        if self.llm is not None:
            try:
                return self._run_llm(question, history or [])
            except Exception as exc:
                res = self._run_offline(question)
                res.error = f"LLM unavailable, used offline mode ({exc})"
                return res
        return self._run_offline(question)

    # -- LLM path
    def _run_llm(self, question: str, history: list[dict]) -> AgentResult:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-6:] + [{"role": "user", "content": question}]
        steps = []
        for _ in range(self.max_iterations):
            resp = self.llm.chat(messages, tools=openai_tool_specs())
            if not resp.tool_calls:
                return AgentResult(resp.content or "I could not produce an answer.", steps, used_llm=True)
            messages.append({"role": "assistant", "content": resp.content or "",
                             "tool_calls": [{"id": c.id, "type": "function",
                                             "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in resp.tool_calls]})
            for c in resp.tool_calls:
                result = call_tool(c.name, c.arguments)
                steps.append({"tool": c.name, "arguments": c.arguments, "result": result})
                messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(result)[:6000]})
        messages.append({"role": "user", "content": "Give your final answer now using the tool results."})
        final = self.llm.chat(messages)
        return AgentResult(final.content or "I reached the step limit before finishing.", steps, used_llm=True)

    # -- offline path
    def _run_offline(self, question: str) -> AgentResult:
        p = parse_request(question)
        q, places, steps = p["text"], p["places"], []

        def use(tool, **args):
            result = call_tool(tool, args)
            steps.append({"tool": tool, "arguments": args, "result": result})
            return result

        asks_knowledge = re.search(r"\b(what is|what are|how does|how do|why|explain|interchange|slab|discount|policy|rules?|"
                                   r"tell me about|network|lines?)\b", q) and len(places) < 2
        if asks_knowledge:
            r = use("search_knowledge", query=question)
            return AgentResult(fmt.format_passages(r.get("passages", [])), steps)

        if len(places) >= 2:
            a, b = places[0], places[1]
            if re.search(r"best time|when should|when to leave|what time|avoid (?:the )?traffic|leave", q):
                r = use("best_departure_time", start=a, destination=b, day_of_week=p["day_of_week"] or 0, rain_level=p["rain_level"])
                return AgentResult(fmt.format_departure(r) if r.get("ok") else r["error"], steps)
            if p["budget"] is not None:
                r = use("plan_within_budget", start=a, destination=b, budget=p["budget"])
                return AgentResult(fmt.format_journey(r["journey"], p["budget"]) if r.get("ok") else r["error"], steps)
            if re.search(r"fare|cost|price|how much|compare|options|modes", q) and not p["hour"]:
                r = use("compare_transport_modes", start=a, destination=b)
                text = fmt.format_modes(a, b, r["options"])
                return AgentResult(text, steps)
            r = use("plan_journey", start=a, destination=b, priority=p["priority"], mode=p["mode"], hour=p["hour"],
                    day_of_week=p["day_of_week"], rain_level=p["rain_level"])
            return AgentResult(fmt.format_journey(r["journey"]) if r.get("ok") else r["error"], steps)

        if p["mode"] and (p["hour"] is not None or re.search(r"delay|traffic|late|slow|rain", q)):
            r = use("predict_delay", mode=p["mode"], hour=p["hour"] if p["hour"] is not None else 9,
                    day_of_week=p["day_of_week"] or 0, rain_level=p["rain_level"])
            return AgentResult(fmt.format_delay(r), steps)

        r = use("search_knowledge", query=question)
        if r.get("passages"):
            return AgentResult(fmt.format_passages(r["passages"]), steps)
        places_text = ", ".join(call_tool("list_places", {}).get("places", []))
        return AgentResult("I can plan journeys, compare fares, predict traffic delays and suggest the best time to leave. "
                           f"Try: 'best way from Egmore to Tambaram at 9 am'. Places I know: {places_text}.", steps)
