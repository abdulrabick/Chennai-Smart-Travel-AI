"""SQLite helpers: create schema, seed it from the CSV files, log usage, run queries."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

import settings

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
ROUTE_COLUMNS = ["start", "destination", "transport_mode", "distance_km",
                 "estimated_time_min", "estimated_fare_inr", "transfer_time_min"]


@contextmanager
def connect(db_path: Path | str | None = None):
    """Open a connection that commits on success and rolls back on error."""
    con = sqlite3.connect(str(db_path or settings.DB_PATH))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(db_path=None, reset: bool = False) -> None:
    """Create all tables and views. reset=True drops the tables managed by this project first."""
    with connect(db_path) as con:
        if reset:
            for view in ("v_mode_summary", "v_hourly_delay"):
                con.execute(f"DROP VIEW IF EXISTS {view}")
            for table in ("feedback", "journey_logs", "chat_logs", "traffic_history", "locations", "transport_routes"):
                con.execute(f"DROP TABLE IF EXISTS {table}")
        else:
            _migrate_legacy_routes_table(con)
        con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def _migrate_legacy_routes_table(con: sqlite3.Connection) -> None:
    """Older versions of the project created transport_routes without a UNIQUE key; rebuild it once."""
    row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transport_routes'").fetchone()
    if row and "UNIQUE" not in row[0].upper():
        old = pd.read_sql_query("SELECT * FROM transport_routes", con)
        con.execute("DROP TABLE transport_routes")
        con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        if len(old):
            _insert_routes(con, old)


def _insert_routes(con: sqlite3.Connection, df: pd.DataFrame) -> int:
    df = df.copy()
    if "transfer_time_min" not in df:
        df["transfer_time_min"] = 0
    df = df[ROUTE_COLUMNS].drop_duplicates(subset=["start", "destination", "transport_mode"])
    before = con.execute("SELECT COUNT(*) FROM transport_routes").fetchone()[0]
    con.executemany(
        """INSERT OR IGNORE INTO transport_routes
           (start, destination, transport_mode, distance_km, estimated_time_min, estimated_fare_inr, transfer_time_min)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        df.itertuples(index=False, name=None),
    )
    return con.execute("SELECT COUNT(*) FROM transport_routes").fetchone()[0] - before


def seed_routes(csv_path=None, db_path=None) -> int:
    """Load data/raw/transport_options.csv (duplicates are ignored). Returns rows inserted."""
    df = pd.read_csv(csv_path or settings.RAW_DIR / "transport_options.csv")
    for col in ("start", "destination", "transport_mode"):
        df[col] = df[col].astype(str).str.strip()
    with connect(db_path) as con:
        return _insert_routes(con, df)


def seed_locations(csv_path=None, db_path=None) -> int:
    df = pd.read_csv(csv_path or settings.PROCESSED_DIR / "location_coordinates.csv")
    df["location"] = df["location"].astype(str).str.strip()
    with connect(db_path) as con:
        con.executemany("INSERT OR REPLACE INTO locations (name, latitude, longitude) VALUES (?, ?, ?)",
                        df[["location", "latitude", "longitude"]].itertuples(index=False, name=None))
    return len(df)


def load_traffic_history(df: pd.DataFrame, db_path=None, replace: bool = True) -> int:
    cols = ["hour", "day_of_week", "month", "rain_level", "mode", "distance_km",
            "base_time_min", "actual_time_min", "delay_ratio"]
    with connect(db_path) as con:
        if replace:
            con.execute("DELETE FROM traffic_history")
        con.executemany(
            f"INSERT INTO traffic_history ({', '.join(cols)}, is_synthetic) VALUES ({', '.join('?' * len(cols))}, 1)",
            df[cols].itertuples(index=False, name=None),
        )
    return len(df)


def query_df(sql: str, params=(), db_path=None) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query(sql, con, params=params)


def log_journey(start, destination, priority=None, mode_filter=None, total_time=None, total_fare=None,
                total_distance=None, used_traffic=False, source="app", db_path=None) -> int:
    with connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO journey_logs (start, destination, priority, mode_filter, total_time_min,
               total_fare_inr, total_distance, used_traffic, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (start, destination, priority, mode_filter, total_time, total_fare, total_distance, int(bool(used_traffic)), source),
        )
        return cur.lastrowid


def log_chat(agent, question, answer, tools_used=None, db_path=None) -> int:
    with connect(db_path) as con:
        cur = con.execute("INSERT INTO chat_logs (agent, question, answer, tools_used) VALUES (?, ?, ?, ?)",
                          (agent, question, answer, ",".join(tools_used or [])))
        return cur.lastrowid


def add_feedback(rating: int, comment: str = "", journey_id: int | None = None, db_path=None) -> int:
    if not 1 <= int(rating) <= 5:
        raise ValueError("rating must be between 1 and 5")
    with connect(db_path) as con:
        cur = con.execute("INSERT INTO feedback (journey_id, rating, comment) VALUES (?, ?, ?)",
                          (journey_id, int(rating), comment))
        return cur.lastrowid


def table_counts(db_path=None) -> dict:
    tables = ["transport_routes", "locations", "traffic_history", "journey_logs", "feedback", "chat_logs"]
    with connect(db_path) as con:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


if __name__ == "__main__":
    init_db()
    print("routes inserted:", seed_routes())
    print("locations:", seed_locations())
    print(table_counts())
