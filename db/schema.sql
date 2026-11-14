-- Chennai Smart Travel AI : SQLite schema
PRAGMA foreign_keys = ON;

-- 1. Route options between two places for each transport mode (loaded from data/raw/transport_options.csv)
CREATE TABLE IF NOT EXISTS transport_routes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    start               TEXT NOT NULL,
    destination         TEXT NOT NULL,
    transport_mode      TEXT NOT NULL,
    distance_km         REAL CHECK (distance_km >= 0),
    estimated_time_min  REAL CHECK (estimated_time_min >= 0),
    estimated_fare_inr  REAL CHECK (estimated_fare_inr >= 0),
    transfer_time_min   REAL DEFAULT 0,
    UNIQUE (start, destination, transport_mode)
);
CREATE INDEX IF NOT EXISTS idx_routes_pair ON transport_routes (start, destination);
CREATE INDEX IF NOT EXISTS idx_routes_mode ON transport_routes (transport_mode);

-- 2. Places with coordinates
CREATE TABLE IF NOT EXISTS locations (
    name       TEXT PRIMARY KEY,
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL
);

-- 3. Observed (or simulated) travel-time history used to train the delay models
CREATE TABLE IF NOT EXISTS traffic_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hour            INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),   -- 0 = Monday
    month           INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    rain_level      INTEGER NOT NULL CHECK (rain_level BETWEEN 0 AND 2),    -- 0 none, 1 light, 2 heavy
    mode            TEXT NOT NULL,
    distance_km     REAL NOT NULL,
    base_time_min   REAL NOT NULL,
    actual_time_min REAL NOT NULL,
    delay_ratio     REAL NOT NULL,                                           -- actual / base
    is_synthetic    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_traffic_mode_hour ON traffic_history (mode, hour);

-- 4. What users searched (powers "popular routes" analytics)
CREATE TABLE IF NOT EXISTS journey_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    start           TEXT NOT NULL,
    destination     TEXT NOT NULL,
    priority        TEXT,
    mode_filter     TEXT,
    total_time_min  REAL,
    total_fare_inr  REAL,
    total_distance  REAL,
    used_traffic    INTEGER DEFAULT 0,
    source          TEXT DEFAULT 'app'
);
CREATE INDEX IF NOT EXISTS idx_journey_pair ON journey_logs (start, destination);

-- 5. User feedback on recommended journeys
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    journey_id  INTEGER REFERENCES journey_logs(id) ON DELETE SET NULL,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT
);

-- 6. Assistant conversations
CREATE TABLE IF NOT EXISTS chat_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    agent       TEXT,
    question    TEXT NOT NULL,
    answer      TEXT,
    tools_used  TEXT
);

-- Views used by the analytics dashboard
CREATE VIEW IF NOT EXISTS v_mode_summary AS
SELECT transport_mode,
       COUNT(*)                                        AS options,
       ROUND(AVG(estimated_fare_inr), 1)               AS avg_fare_inr,
       ROUND(AVG(estimated_time_min), 1)               AS avg_time_min,
       ROUND(AVG(distance_km), 1)                      AS avg_distance_km,
       ROUND(AVG(estimated_fare_inr / NULLIF(distance_km, 0)), 2) AS fare_per_km,
       ROUND(AVG(distance_km / NULLIF(estimated_time_min, 0) * 60), 1) AS avg_speed_kmph
FROM transport_routes
GROUP BY transport_mode;

CREATE VIEW IF NOT EXISTS v_hourly_delay AS
SELECT mode, hour,
       ROUND(AVG(delay_ratio), 3) AS avg_delay_ratio,
       COUNT(*)                   AS samples
FROM traffic_history
GROUP BY mode, hour;
