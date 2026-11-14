"""REST API (FastAPI).   pip install fastapi     then     uvicorn backend.api.main:app --reload
Interactive docs: http://127.0.0.1:8000/docs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services import analytics_service, assistant_service, route_service, traffic_service
from backend.services.bootstrap import ensure_ready
from db import database as dbm
from ml import predictor

app = FastAPI(title="Chennai Smart Travel AI", version="1.0",
              description="Multi-modal route planning, ML traffic-delay prediction, SQL analytics and an AI travel assistant.")


class Traffic(BaseModel):
    hour: int = Field(9, ge=0, le=23)
    day_of_week: int = Field(0, ge=0, le=6, description="0 = Monday")
    month: int = Field(1, ge=1, le=12)
    rain_level: int = Field(0, ge=0, le=2, description="0 none, 1 light, 2 heavy")


class RouteRequest(BaseModel):
    start: str
    destination: str
    priority: str = "Fastest"
    fare_type: str = "regular"
    mode: str | None = None
    traffic: Traffic | None = None


class DelayRequest(Traffic):
    mode: str
    distance_km: float = 8.0
    base_time_min: float = 20.0


class AskRequest(BaseModel):
    question: str
    mode: str = Field("agent", description="agent | multi | rag")


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    journey_id: int | None = None


@app.on_event("startup")
def startup():
    ensure_ready(train_if_missing=True)


@app.get("/health")
def health():
    return {"status": "ok", "predictor": predictor.model_info(), "llm": assistant_service.llm_status(), "tables": dbm.table_counts()}


@app.get("/locations")
def locations(network_only: bool = True):
    return {"locations": route_service.list_locations(network_only)}


@app.post("/route")
def route(req: RouteRequest):
    res = route_service.plan_route(req.start, req.destination, req.priority, req.fare_type, req.mode,
                                   req.traffic.model_dump() if req.traffic else None, source="api")
    if not res["ok"]:
        raise HTTPException(status_code=404, detail=res["error"])
    return res["journey"]


@app.post("/route/compare")
def route_compare(req: RouteRequest):
    res = route_service.compare_priorities(req.start, req.destination, req.fare_type, req.mode,
                                           req.traffic.model_dump() if req.traffic else None)
    if not res["ok"]:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.get("/fares")
def fares(start: str, destination: str):
    return {"direct_options": route_service.direct_options(start, destination).to_dict("records")}


@app.post("/predict-delay")
def predict_delay(req: DelayRequest):
    return traffic_service.predict_delay(req.mode, req.hour, req.day_of_week, req.month, req.rain_level,
                                         req.distance_km, req.base_time_min)


@app.get("/best-departure")
def best_departure(start: str, destination: str, day_of_week: int = 0, month: int = 1, rain_level: int = 0):
    res = traffic_service.best_departure(start, destination, day_of_week, month, rain_level)
    if not res["ok"]:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.post("/ask")
def ask(req: AskRequest):
    return assistant_service.ask(req.question, req.mode)


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    return {"id": dbm.add_feedback(req.rating, req.comment, req.journey_id)}


@app.get("/analytics/summary")
def analytics_summary():
    return {"tables": analytics_service.overview(),
            "modes": analytics_service.mode_summary().to_dict("records"),
            "reliability": analytics_service.reliability_by_mode().to_dict("records"),
            "popular_routes": analytics_service.popular_routes().to_dict("records")}
