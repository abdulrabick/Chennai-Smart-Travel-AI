"""Create a supervised fine-tuning dataset (chat JSONL) from the route engine and traffic model.

    python -m genai.finetune.make_dataset

Every answer is produced by the verified engine, so a small model fine-tuned on this file (LoRA / QLoRA, see
train_lora.py) learns to answer Chennai route questions in the project's format with grounded numbers.
"""
from __future__ import annotations

import json
import random

import settings
from backend.services import route_service
from genai.agents import formatting as fmt
from ml.predictor import TrafficContext, RAIN_LABELS, DAY_LABELS

SYSTEM = "You are Chennai Smart Travel AI. Answer with the route, fare and time. Figures are prototype estimates."
HOURS = {7: "7 am", 9: "9 am", 13: "1 pm", 18: "6 pm", 21: "9 pm"}


def _examples(seed: int = 7):
    rng = random.Random(seed)
    places = route_service.list_locations(network_only=True)
    pairs = [(a, b) for a in places for b in places if a != b]
    for a, b in pairs:
        for priority in route_service.PRIORITIES:
            res = route_service.plan_route(a, b, priority, log=False)
            if res["ok"]:
                q = rng.choice([f"What is the {priority.lower()} way from {a} to {b}?",
                                f"I want to go from {a} to {b}. Suggest the {priority.lower()} option.",
                                f"{priority} route {a} to {b} please"])
                yield q, fmt.format_journey(res["journey"])
        hour = rng.choice(list(HOURS))
        rain = rng.choice([0, 1, 2])
        ctx = TrafficContext(hour, rng.randint(0, 6), rng.randint(1, 12), rain)
        res = route_service.plan_route(a, b, "Fastest", traffic=ctx, log=False)
        if res["ok"]:
            when = f"{DAY_LABELS[ctx.day_of_week]} at {HOURS[hour]}" + ("" if rain == 0 else f" in {RAIN_LABELS[rain].lower()}")
            yield f"Fastest way from {a} to {b} on {when}?", fmt.format_journey(res["journey"])


def build(path=None, val_fraction: float = 0.1) -> dict:
    rows = [{"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q},
                          {"role": "assistant", "content": a}]} for q, a in _examples()]
    random.Random(1).shuffle(rows)
    n_val = max(1, int(len(rows) * val_fraction))
    out = path or settings.FINETUNE_DIR / "chennai_travel_sft"
    out.mkdir(parents=True, exist_ok=True)
    for name, part in (("train.jsonl", rows[n_val:]), ("val.jsonl", rows[:n_val])):
        with open(out / name, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in part)
    return {"train": len(rows) - n_val, "val": n_val, "dir": str(out)}


if __name__ == "__main__":
    print(build())
