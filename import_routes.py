import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "raw" / "transport_options.csv"
DB_FILE = BASE_DIR / "chennai_travel.db"

df = pd.read_csv(CSV_FILE)

connection = sqlite3.connect(DB_FILE)

try:
    cursor = connection.cursor()

    # Remove existing route records
    cursor.execute("DELETE FROM transport_routes")

    # Import fresh CSV data
    df.to_sql(
        "transport_routes",
        connection,
        if_exists="append",
        index=False
    )

    connection.commit()
    print("Transport data refreshed successfully!")
    print("Total routes:", len(df))

except Exception:
    connection.rollback()
    raise

finally:
    connection.close()