"""Central paths and tunables for Chennai Smart Travel AI."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chennai_travel.db"
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"      # drop official CMRL / MTC / Southern Railway notes here (.md .txt .pdf)
MODEL_DIR = BASE_DIR / "ml" / "models"
DELAY_MODEL_PATH = MODEL_DIR / "delay_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
TRAFFIC_CSV = PROCESSED_DIR / "traffic_history.csv"
FINETUNE_DIR = BASE_DIR / "genai" / "finetune"

# peak hours used by SQL analytics (local time, 24h clock)
PEAK_HOURS = (8, 9, 10, 17, 18, 19, 20)
