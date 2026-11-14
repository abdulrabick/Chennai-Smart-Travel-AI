"""Multi-agent trip planner (CrewAI / A2A-style, written in plain Python so it has no extra dependency).

    Planner  ->  RouteAnalyst  ->  Critic  ->  Explainer

Agents exchange AgentMessage objects (sender, recipient, content, data). The Planner turns the request into tasks, the
RouteAnalyst runs tools, the Critic checks the options against the user's constraints (budget, rain, rush hour) and picks
one, and the Explainer writes the final answer (with the LLM when available, otherwise a template).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from genai.agents import formatting as fmt
from genai.agents.smart_agent import parse_request
from genai.agents.tools import call_tool


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    content: str
    data: dict = field(default_factory=dict)


@dataclass
class MultiAgentResult:
    answer: str
    messages: list[AgentMessage]
    verdict: dict
    used_llm: bool = False

    def transcript(self) -> list[dict]:
        return [asdict(m) for m in self.messages]


class PlannerAgent:
    name = "Planner"

    def run(self, question: str) -> AgentMessage:
        p = parse_request(question)
        if len(p["places"]) < 2:
            return AgentMessage(self.name, "User", "I need a start and a destination, e.g. 'from Egmore to Tambaram'.", {"ok": False})
        tasks = ["fastest", "cheapest"]
        if p["hour"] is not None or p["rain_level"]:
            tasks.append("traffic_check")
        tasks.append("best_departure")
        return AgentMessage(self.name, "RouteAnalyst", f"Plan {p['places'][0]} to {p['places'][1]}: tasks {tasks}.",
                            {"ok": True, "request": p, "tasks": tasks})


class RouteAnalystAgent:
    name = "RouteAnalyst"

    def run(self, plan: AgentMessage) -> AgentMessage:
        p = plan.data["request"]
        a, b = p["places"][:2]
        hour = p["hour"]
        common = dict(hour=hour, day_of_week=p["day_of_week"], rain_level=p["rain_level"])
        data = {
            "fastest": call_tool("plan_journey", {"start": a, "destination": b, "priority": "Fastest", **common}),
            "cheapest": call_tool("plan_journey", {"start": a, "destination": b, "priority": "Cheapest", **common}),
            "best_departure": call_tool("best_departure_time", {"start": a, "destination": b,
                                                                "day_of_week": p["day_of_week"] or 0, "rain_level": p["rain_level"]}),
        }
        if "traffic_check" in plan.data["tasks"]:
            modes = [m for m in ("MTC Bus", "Cab", "Local Train", "Metro")]
            data["delay_check"] = [call_tool("predict_delay", {"mode": m, "hour": hour if hour is not None else 9,
                                                               "day_of_week": p["day_of_week"] or 0, "rain_level": p["rain_level"]})
                                   for m in modes]
        return AgentMessage(self.name, "Critic", "Collected fastest, cheapest and timing options.", data)


class CriticAgent:
    name = "Critic"

    def run(self, request: dict, analysis: AgentMessage) -> AgentMessage:
        d = analysis.data
        fast, cheap = d["fastest"], d["cheapest"]
        if not (fast.get("ok") and cheap.get("ok")):
            return AgentMessage(self.name, "Explainer", "No valid route found.", {"ok": False, "error": (fast if not fast.get("ok") else cheap).get("error")})
        f, c = fast["journey"], cheap["journey"]
        notes, budget = [], request["budget"]
        choice, reason = f, "fastest option"
        if budget is not None:
            if f["total_fare_inr"] <= budget:
                reason = f"fastest option and it fits your Rs.{budget:.0f} budget"
            elif c["total_fare_inr"] <= budget:
                choice, reason = c, f"the fastest option costs Rs.{f['total_fare_inr']:.0f}, over your Rs.{budget:.0f} budget, so I chose the cheapest"
            else:
                choice, reason = c, f"nothing fits Rs.{budget:.0f}; the cheapest costs Rs.{c['total_fare_inr']:.0f}"
                notes.append("Budget too low for this trip.")
        elif c["total_fare_inr"] < f["total_fare_inr"] and c["total_minutes"] - f["total_minutes"] <= 5:
            choice, reason = c, "cheapest option, only a few minutes slower than the fastest"
        for dl in d.get("delay_check", []):
            if dl.get("ok") and dl["delay_level"] == "high" and dl["mode"] in choice["transport_used"]:
                notes.append(f"{dl['mode']} is expected to run {dl['extra_minutes']:.0f} min late then ({dl['when']}).")
        bd = d.get("best_departure", {})
        if bd.get("ok") and bd["minutes_saved"] >= 3 and request["hour"] is not None and request["hour"] != bd["best_hour"]:
            notes.append(f"Leaving around {bd['best_hour']:02d}:00 instead would save about {bd['minutes_saved']:.0f} min.")
        verdict = {"ok": True, "choice": choice, "reason": reason, "notes": notes, "alternative_fastest": f, "alternative_cheapest": c}
        return AgentMessage(self.name, "Explainer", f"Recommend the {reason}.", verdict)


class ExplainerAgent:
    name = "Explainer"

    def __init__(self, llm=None):
        self.llm = llm

    def run(self, review: AgentMessage) -> tuple[str, bool]:
        v = review.data
        if not v.get("ok"):
            return v.get("error") or review.content, False
        base = fmt.format_journey(v["choice"])
        text = f"Recommendation: {v['reason']}.\n\n{base}"
        if v["notes"]:
            text += "\n\nThings to watch:\n" + "\n".join(f"- {n}" for n in v["notes"])
        if self.llm is not None:
            try:
                r = self.llm.chat([
                    {"role": "system", "content": "You are Chennai Smart Travel AI. Rewrite the verified trip plan in friendly simple English. "
                                                  "Never change any number, place or transport mode. Mention it is a prototype estimate."},
                    {"role": "user", "content": json.dumps({"reason": v["reason"], "notes": v["notes"], "journey": v["choice"]})[:5000]}])
                if r.content:
                    return r.content, True
            except Exception as exc:
                print(f"[multi_agent] explainer LLM failed: {exc}")
        return text, False


class MultiAgentTripPlanner:
    def __init__(self, llm=None):
        self.planner, self.analyst, self.critic, self.explainer = PlannerAgent(), RouteAnalystAgent(), CriticAgent(), ExplainerAgent(llm)

    def run(self, question: str) -> MultiAgentResult:
        msgs = []
        plan = self.planner.run(question)
        msgs.append(plan)
        if not plan.data.get("ok"):
            return MultiAgentResult(plan.content, msgs, {"ok": False})
        analysis = self.analyst.run(plan)
        msgs.append(analysis)
        review = self.critic.run(plan.data["request"], analysis)
        msgs.append(review)
        answer, used_llm = self.explainer.run(review)
        msgs.append(AgentMessage("Explainer", "User", answer))
        return MultiAgentResult(answer, msgs, review.data, used_llm)
