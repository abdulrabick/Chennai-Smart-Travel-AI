"""First-time setup (safe to re-run):  python setup_project.py

Creates the SQL schema, loads routes and places, simulates the traffic history, trains the delay models
and builds the fine-tuning dataset.  --retrain forces the models to be trained again.
"""
import sys

import settings
from backend.services.bootstrap import ensure_ready
from ml import predictor


def main():
    if "--retrain" in sys.argv and settings.DELAY_MODEL_PATH.exists():
        settings.DELAY_MODEL_PATH.unlink()
        predictor.reload_model()
    info = ensure_ready(train_if_missing=True, verbose=True)
    from genai.finetune.make_dataset import build
    print("fine-tuning dataset:", build())
    print("\nReady:", info)
    print("Next:  streamlit run frontend/app.py     (API: uvicorn backend.api.main:app --reload)")


if __name__ == "__main__":
    main()
