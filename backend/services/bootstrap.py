"""One place that makes sure the database, traffic history and ML model exist (safe to call on every start-up)."""
from __future__ import annotations

import pandas as pd

import settings
from db import database as dbm
from ml import predictor
from ml.traffic_data import generate_traffic_history


def ensure_ready(train_if_missing: bool = True, verbose: bool = False) -> dict:
    log = print if verbose else (lambda *a, **k: None)
    dbm.init_db()
    counts = dbm.table_counts()
    if counts["transport_routes"] == 0:
        log("seeding routes:", dbm.seed_routes())
    if counts["locations"] == 0:
        log("seeding locations:", dbm.seed_locations())
    if not settings.TRAFFIC_CSV.exists():
        log("simulating traffic history ...")
        generate_traffic_history().to_csv(settings.TRAFFIC_CSV, index=False)
    if counts["traffic_history"] == 0:
        log("loading traffic history into SQL:", dbm.load_traffic_history(pd.read_csv(settings.TRAFFIC_CSV)))
    if train_if_missing and not settings.DELAY_MODEL_PATH.exists():
        from ml.training.train_delay_model import train
        log("training delay models ...")
        train(verbose=verbose)
        predictor.reload_model()
    return {"counts": dbm.table_counts(), "predictor": predictor.model_info()}
