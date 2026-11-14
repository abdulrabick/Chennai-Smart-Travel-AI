"""Tests for the ML, SQL, routing, RAG, agent and API-service layers.

    python tests/test_smart_travel_ai.py        (or)        python -m pytest tests/test_smart_travel_ai.py -q
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

import settings
from backend.services import analytics_service as an, route_service as rs, traffic_service as ts
from backend.services.bootstrap import ensure_ready
from db import database as dbm
from genai.agents import tools
from genai.agents.multi_agent import MultiAgentTripPlanner
from genai.agents.smart_agent import SmartTravelAgent, parse_request
from genai.llm_client import LLMResponse, ToolCall
from genai.rag.retriever import KnowledgeRetriever, get_retriever
from genai.rag.knowledge_base import Document
from ml import predictor
from ml.predictor import TrafficContext
from ml.traffic_data import expected_ratio, generate_traffic_history

ensure_ready(train_if_missing=True)


# ----------------------------------------------------------------------------- SQL
def _tmp_db():
    return Path(tempfile.mkdtemp()) / "t.db"


def test_schema_seed_and_idempotence():
    db = _tmp_db()
    dbm.init_db(db)
    first = dbm.seed_routes(db_path=db)
    assert first > 0 and dbm.seed_routes(db_path=db) == 0          # second seed adds nothing (UNIQUE key)
    dbm.init_db(db)                                                 # re-running init keeps the data
    assert dbm.table_counts(db)["transport_routes"] == first


def test_legacy_table_is_migrated_and_deduplicated():
    db = _tmp_db()
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE transport_routes (id INTEGER PRIMARY KEY AUTOINCREMENT, start TEXT, destination TEXT,
                   transport_mode TEXT, distance_km REAL, estimated_time_min REAL, estimated_fare_inr REAL, transfer_time_min REAL)""")
    row = ("A", "B", "Bus", 5.0, 10.0, 10.0, 0.0)
    con.executemany("INSERT INTO transport_routes (start,destination,transport_mode,distance_km,estimated_time_min,estimated_fare_inr,transfer_time_min) VALUES (?,?,?,?,?,?,?)", [row, row])
    con.commit(); con.close()
    dbm.init_db(db)
    assert dbm.table_counts(db)["transport_routes"] == 1


def test_constraints_reject_bad_data():
    db = _tmp_db(); dbm.init_db(db)
    try:
        dbm.add_feedback(9, "bad", db_path=db); raise AssertionError("rating 9 accepted")
    except ValueError:
        pass
    try:
        with dbm.connect(db) as con:
            con.execute("INSERT INTO traffic_history (hour,day_of_week,month,rain_level,mode,distance_km,base_time_min,actual_time_min,delay_ratio) VALUES (30,0,1,0,'Bus',1,1,1,1)")
        raise AssertionError("hour 30 accepted")
    except sqlite3.IntegrityError:
        pass


def test_logging_helpers():
    db = _tmp_db(); dbm.init_db(db)
    jid = dbm.log_journey("A", "B", "Fastest", None, 10, 20, 5, True, db_path=db)
    dbm.add_feedback(5, "great", jid, db_path=db)
    dbm.log_chat("agent", "q", "a", ["plan_journey"], db_path=db)
    c = dbm.table_counts(db)
    assert c["journey_logs"] == c["feedback"] == c["chat_logs"] == 1


# ----------------------------------------------------------------------------- ML
def test_simulated_traffic_has_the_assumed_patterns():
    assert expected_ratio("MTC Bus", 9, 0, 6, 0) > expected_ratio("MTC Bus", 14, 0, 6, 0)       # rush hour is slower
    assert expected_ratio("MTC Bus", 9, 0, 6, 2) > expected_ratio("MTC Bus", 9, 0, 6, 0)        # rain is slower
    assert expected_ratio("Metro", 9, 0, 6, 2) < 1.1                                              # metro barely affected
    df = generate_traffic_history(3000, seed=1)
    assert len(df) == 3000 and df["delay_ratio"].min() >= 0.9 and set(df["rain_level"]) <= {0, 1, 2}


def test_models_beat_the_naive_baseline():
    from ml.training.train_delay_model import train
    rep = train(generate_traffic_history(6000, seed=3), save=False, verbose=False)
    naive = rep["results"]["Naive mean"]["mae_ratio"]
    assert rep["results"][rep["best_model"]]["mae_ratio"] < 0.8 * naive
    assert "Neural Network (MLP)" in rep["results"]
    assert next(iter(rep["feature_importance"])) in {"mode", "is_peak", "hour_sin", "hour_cos", "rain_level", "base_time_min"}


def test_predictor_learned_the_patterns():
    bus_peak = predictor.predict_ratio("MTC Bus", TrafficContext(9, 0, 11, 0))
    bus_calm = predictor.predict_ratio("MTC Bus", TrafficContext(14, 0, 11, 0))
    bus_rain = predictor.predict_ratio("MTC Bus", TrafficContext(14, 0, 11, 2))
    metro = predictor.predict_ratio("Metro", TrafficContext(9, 0, 11, 2))
    assert bus_peak > bus_calm + 0.15 and bus_rain > bus_calm + 0.15 and metro < 1.15


def test_fallback_predictor_when_model_missing():
    import shutil
    saved = settings.DELAY_MODEL_PATH.with_suffix(".bak")
    shutil.move(settings.DELAY_MODEL_PATH, saved)
    predictor.reload_model()
    try:
        assert predictor.model_info()["source"] == "rule-based fallback"
        assert predictor.predict_ratio("Cab", TrafficContext(9, 0, 11, 2)) > 1.3
    finally:
        shutil.move(saved, settings.DELAY_MODEL_PATH)
        predictor.reload_model()
    assert predictor.model_info()["source"] == "trained model"


def test_context_validation():
    for bad in ((24, 0, 1, 0), (9, 7, 1, 0), (9, 0, 13, 0), (9, 0, 1, 3)):
        try:
            TrafficContext(*bad); raise AssertionError(bad)
        except ValueError:
            pass


# ----------------------------------------------------------------------------- routing
def test_traffic_makes_road_trips_slower_but_not_the_graph_in_place():
    from transport_engine import build_transport_graph
    g = build_transport_graph()
    before = sorted(d["time"] for _, _, d in g.edges(data=True))
    g2 = predictor.adjust_graph_times(g, TrafficContext(9, 0, 11, 2))
    assert sorted(d["time"] for _, _, d in g.edges(data=True)) == before          # original untouched
    assert sum(d["time"] for _, _, d in g2.edges(data=True)) > sum(before)


def test_traffic_aware_route_is_never_faster_than_scheduled():
    free = rs.plan_route("Egmore", "Tambaram", "Fastest", log=False)["journey"]
    busy = rs.plan_route("Egmore", "Tambaram", "Fastest", traffic=TrafficContext(18, 1, 11, 2), log=False)["journey"]
    assert busy["total_minutes"] >= free["total_minutes"] and busy["traffic"]


def test_route_service_validation_and_fuzzy_match():
    assert rs.resolve_location("tambaram") == "Tambaram" and rs.resolve_location("guindi") == "Guindy"
    assert rs.resolve_location("Atlantis") is None
    assert not rs.plan_route("Egmore", "Egmore")["ok"] and not rs.plan_route("Egmore", "Atlantis")["ok"]
    assert not rs.plan_route("Egmore", "Guindy", "Quickest")["ok"]
    assert rs.plan_within_budget("Washermenpet", "Guindy", 5)["ok"] is False
    assert rs.plan_within_budget("Washermenpet", "Guindy", 100)["ok"]


def test_best_departure_avoids_rush_hour():
    b = ts.best_departure("Egmore", "Tambaram", 0, 11, 2)
    assert b["ok"] and b["best_hour"] not in (8, 9, 18, 19) and b["minutes_saved"] >= 0


# ----------------------------------------------------------------------------- SQL analytics
def test_analytics_queries():
    ms = an.mode_summary(); assert {"Metro", "MTC Bus"} <= set(ms["transport_mode"])
    pk = an.peak_vs_offpeak().set_index("mode"); assert (pk["peak_ratio"] > pk["offpeak_ratio"]).all()
    rk = an.mode_rankings(); assert rk["fare_rank"].min() == 1 and (rk.groupby("route")["fare_rank"].min() == 1).all()
    assert an.reliability_by_mode().set_index("mode").loc["Metro", "pct_trips_over_25pct_late"] < 1
    assert len(an.delay_by_hour()) > 100


# ----------------------------------------------------------------------------- RAG
def test_retriever_finds_the_right_source():
    r = get_retriever(rebuild=True)
    assert r.search("discounted metro fare")[0].source == "generated/metro_fares"
    assert r.search("which stations are interchanges")[0].source == "generated/metro_network"
    assert r.search("zzzzqqq nonsense") == []


def test_retriever_indexes_user_documents():
    r = KnowledgeRetriever([Document("knowledge/x.md", "Night buses", "Night owl buses run after midnight on selected corridors.")])
    assert r.search("night owl bus")[0].source == "knowledge/x.md"


# ----------------------------------------------------------------------------- agents
class FakeLLM:
    """Scripted LLM: first asks for a tool, then answers using the tool result."""
    def __init__(self): self.calls = 0
    def chat(self, messages, tools=None, **kw):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(None, [ToolCall("c1", "plan_journey", {"start": "Egmore", "destination": "Guindy", "hour": 9, "bogus": 1})])
        tool_msg = [m for m in messages if m["role"] == "tool"][-1]
        return LLMResponse("Take the " + json.loads(tool_msg["content"])["journey"]["transport_used"][0] + ".")


class BrokenLLM:
    def chat(self, *a, **k): raise RuntimeError("quota exceeded")


def test_agent_llm_tool_loop():
    res = SmartTravelAgent(FakeLLM()).run("how do I get from Egmore to Guindy?")
    assert res.used_llm and res.answer.startswith("Take the") and res.steps[0]["tool"] == "plan_journey"


def test_agent_falls_back_when_llm_fails():
    res = SmartTravelAgent(BrokenLLM()).run("best way from Egmore to Guindy")
    assert not res.used_llm and "Egmore" in res.answer and "quota" in res.error


def test_offline_agent_routing_of_intents():
    a = SmartTravelAgent()
    cases = {"best way from Egmore to Tambaram at 9 am in heavy rain": "plan_journey",
             "when should I leave from Egmore to Guindy": "best_departure_time",
             "how much does it cost from Guindy to Airport": "compare_transport_modes",
             "will a bus be late at 6 pm in the rain": "predict_delay",
             "what is the discounted metro fare": "search_knowledge",
             "cheapest way from Washermenpet to Guindy under 40": "plan_within_budget"}
    for q, tool in cases.items():
        assert a.run(q).steps[0]["tool"] == tool, q
    assert "Places I know" in a.run("hello").answer


def test_request_parsing():
    p = parse_request("from Egmore to Tambaram at 6 pm in heavy rain under Rs 50 on friday")
    assert p["places"] == ["Egmore", "Tambaram"] and p["hour"] == 18 and p["rain_level"] == 2
    assert p["budget"] == 50 and p["day_of_week"] == 4
    assert parse_request("12 am")["hour"] == 0 and parse_request("12 pm")["hour"] == 12


def test_tool_errors_are_data_not_exceptions():
    assert not tools.call_tool("nope", {})["ok"]
    assert not tools.call_tool("plan_journey", {"start": "Egmore"})["ok"]                 # missing argument
    assert tools.call_tool("plan_journey", {"start": "Egmore", "destination": "Guindy", "evil": "x"})["ok"]


def test_multi_agent_respects_budget():
    ok = MultiAgentTripPlanner().run("go from Washermenpet to Guindy, budget 100")
    assert ok.verdict["ok"] and "fits" in ok.verdict["reason"]
    low = MultiAgentTripPlanner().run("go from Washermenpet to Guindy, budget 5")
    assert any("Budget too low" in n for n in low.verdict["notes"])
    assert [m.sender for m in ok.messages] == ["Planner", "RouteAnalyst", "Critic", "Explainer"]
    assert not MultiAgentTripPlanner().run("take me somewhere").verdict["ok"]


# ----------------------------------------------------------------------------- fine-tuning dataset
def test_finetune_dataset_is_valid_chat_jsonl():
    from genai.finetune.make_dataset import build
    out = Path(tempfile.mkdtemp())
    info = build(out)
    rows = [json.loads(l) for l in (out / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    assert info["train"] == len(rows) > 100
    assert all([m["role"] for m in r["messages"]] == ["system", "user", "assistant"] for r in rows)
    assert all("prototype estimates" in r["messages"][2]["content"] for r in rows)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as exc:
            failed += 1; print("FAIL", fn.__name__, "->", repr(exc))
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
