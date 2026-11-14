"""Train and compare delay-prediction models, then save the best one.

    python -m ml.training.train_delay_model

Models compared (target = delay_ratio):
  * Ridge regression                    - linear baseline
  * Random Forest                       - bagged trees
  * Gradient Boosting (HistGB)          - boosted trees
  * Neural network (MLPRegressor)       - the deep-learning model (scikit-learn, 2 hidden layers)
A PyTorch version of the neural network is in ml/training/train_torch_mlp.py.
"""
from __future__ import annotations

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import settings
from ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_features
from ml.traffic_data import generate_traffic_history


def make_models(seed: int = 42) -> dict:
    def prep(scale: bool):
        num = StandardScaler() if scale else "passthrough"
        return ColumnTransformer([
            ("mode", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", num, NUMERIC_FEATURES),
        ])
    return {
        "Ridge (baseline)": Pipeline([("prep", prep(True)), ("model", Ridge(alpha=1.0))]),
        "Random Forest": Pipeline([("prep", prep(False)),
                                   ("model", RandomForestRegressor(n_estimators=150, min_samples_leaf=3, n_jobs=-1, random_state=seed))]),
        "Gradient Boosting": Pipeline([("prep", prep(False)),
                                       ("model", HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, random_state=seed))]),
        "Neural Network (MLP)": Pipeline([("prep", prep(True)),
                                          ("model", MLPRegressor(hidden_layer_sizes=(64, 32), activation="relu", alpha=1e-4,
                                                                 early_stopping=True, max_iter=300, random_state=seed))]),
    }


def evaluate(model, X_test, y_test, base_time) -> dict:
    pred = model.predict(X_test)
    return {
        "mae_ratio": float(mean_absolute_error(y_test, pred)),
        "rmse_ratio": float(np.sqrt(mean_squared_error(y_test, pred))),
        "r2": float(r2_score(y_test, pred)),
        "mae_minutes": float(np.mean(np.abs((pred - y_test) * base_time))),
    }


def train(df: pd.DataFrame | None = None, n_rows: int = 30000, save: bool = True, seed: int = 42, verbose: bool = True) -> dict:
    if df is None:
        df = pd.read_csv(settings.TRAFFIC_CSV) if settings.TRAFFIC_CSV.exists() else generate_traffic_history(n_rows, seed)
    X = build_features(df)
    y = df["delay_ratio"].astype(float)
    X_tr, X_te, y_tr, y_te, bt_tr, bt_te = train_test_split(X, y, df["base_time_min"].astype(float), test_size=0.2, random_state=seed)

    results, fitted = {}, {}
    # reference point: always predicting the average ratio
    naive = np.full(len(y_te), y_tr.mean())
    results["Naive mean"] = {"mae_ratio": float(mean_absolute_error(y_te, naive)),
                             "rmse_ratio": float(np.sqrt(mean_squared_error(y_te, naive))), "r2": 0.0,
                             "mae_minutes": float(np.mean(np.abs((naive - y_te) * bt_te))), "fit_seconds": 0.0}
    for name, pipe in make_models(seed).items():
        t0 = time.time()
        pipe.fit(X_tr, y_tr)
        res = evaluate(pipe, X_te, y_te, bt_te)
        res["fit_seconds"] = round(time.time() - t0, 2)
        results[name], fitted[name] = res, pipe
        if verbose:
            print(f"{name:24s} MAE(ratio)={res['mae_ratio']:.4f}  MAE(min)={res['mae_minutes']:.2f}  R2={res['r2']:.3f}  ({res['fit_seconds']}s)")

    best_name = min(fitted, key=lambda n: results[n]["mae_ratio"])
    best = fitted[best_name]
    sample = X_te.sample(min(1500, len(X_te)), random_state=seed)
    imp = permutation_importance(best, sample, y_te.loc[sample.index], n_repeats=3, random_state=seed, scoring="neg_mean_absolute_error")
    importance = dict(sorted(zip(X.columns, map(float, imp.importances_mean)), key=lambda kv: -kv[1]))

    report = {"best_model": best_name, "train_rows": int(len(X_tr)), "test_rows": int(len(X_te)),
              "data_is_synthetic": True, "results": results, "feature_importance": importance,
              "target": "delay_ratio = actual_time / scheduled_time"}
    if save:
        settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": best, "name": best_name, "features": list(X.columns)}, settings.DELAY_MODEL_PATH)
        settings.METRICS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if verbose:
            print(f"\nBest model: {best_name} -> saved to {settings.DELAY_MODEL_PATH}")
    return report


if __name__ == "__main__":
    train()
