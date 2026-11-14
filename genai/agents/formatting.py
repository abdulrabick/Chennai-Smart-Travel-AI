"""Turn tool results into plain-English text (used by the offline agent and the fine-tuning dataset)."""
from __future__ import annotations

DISCLAIMER = "These are prototype estimates, not live fares or live traffic."


def _money(x) -> str:
    return f"Rs.{float(x):.0f}"


def format_journey(j: dict, budget: float | None = None) -> str:
    lines = [f"Best {j.get('priority', '').lower()} option from {j['start']} to {j['destination']}: " 
             f"{j['total_minutes']:.0f} min, {_money(j['total_fare_inr'])}, {j['total_distance_km']:.1f} km."]
    for i, s in enumerate(j["steps"], 1):
        extra = ""
        if s.get("metro_lines"):
            extra = f" on the {' / '.join(s['metro_lines'])} ({s.get('stops', 0)} stops)"
        lines.append(f"{i}. {s['from']} to {s['to']} by {s['transport']}{extra}: {s['minutes']:.0f} min, {_money(s['fare_inr'])}.")
    if j.get("traffic"):
        lines.append(f"Times include predicted traffic for {j['traffic']}.")
    if budget is not None:
        lines.append(f"Budget left: {_money(budget - j['total_fare_inr'])} of {_money(budget)}.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def format_modes(start: str, destination: str, rows: list[dict]) -> str:
    if not rows:
        return f"No direct option between {start} and {destination} in the dataset."
    out = [f"Direct options between {start} and {destination} (cheapest first):"]
    out += [f"- {r['mode']}: {_money(r['fare_inr'])}, {r['minutes']:.0f} min, {r['distance_km']:.1f} km" for r in rows]
    out.append(DISCLAIMER)
    return "\n".join(out)


def format_delay(d: dict) -> str:
    return (f"{d['mode']} on {d['when']}: scheduled {d['scheduled_minutes']:.0f} min, expected {d['expected_minutes']:.0f} min "
            f"(+{d['extra_minutes']:.0f} min, delay level {d['delay_level']}). {DISCLAIMER}")


def format_departure(b: dict) -> str:
    return (f"For {b['start']} to {b['destination']} ({b['when']}), leaving around {b['best_hour']:02d}:00 is fastest at "
            f"{b['best_minutes']:.0f} min; leaving around {b['worst_hour']:02d}:00 is slowest at {b['worst_minutes']:.0f} min. "
            f"Choosing the better hour saves about {b['minutes_saved']:.0f} min. {DISCLAIMER}")


def format_passages(passages: list[dict]) -> str:
    if not passages:
        return "I could not find that in the knowledge base."
    return "\n\n".join(f"{p['text']}\n(source: {p['title']})" for p in passages[:2])
