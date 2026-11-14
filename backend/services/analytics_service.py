"""SQL analytics. Every function is one readable query (joins, window functions, CTEs) returning a DataFrame."""
from __future__ import annotations

import pandas as pd

import settings
from db.database import query_df

_PEAK = ", ".join(str(h) for h in settings.PEAK_HOURS)


def mode_summary() -> pd.DataFrame:
    return query_df("SELECT * FROM v_mode_summary ORDER BY fare_per_km")


def delay_by_hour() -> pd.DataFrame:
    return query_df("SELECT mode, hour, avg_delay_ratio FROM v_hourly_delay ORDER BY mode, hour")


def delay_by_rain() -> pd.DataFrame:
    return query_df("""
        SELECT mode,
               CASE rain_level WHEN 0 THEN 'No rain' WHEN 1 THEN 'Light rain' ELSE 'Heavy rain' END AS rain,
               ROUND(AVG(delay_ratio), 3) AS avg_delay_ratio, COUNT(*) AS samples
        FROM traffic_history GROUP BY mode, rain_level ORDER BY mode, rain_level""")


def peak_vs_offpeak() -> pd.DataFrame:
    return query_df(f"""
        SELECT mode,
               ROUND(AVG(CASE WHEN hour IN ({_PEAK}) AND day_of_week < 5 THEN delay_ratio END), 3) AS peak_ratio,
               ROUND(AVG(CASE WHEN NOT (hour IN ({_PEAK}) AND day_of_week < 5) THEN delay_ratio END), 3) AS offpeak_ratio
        FROM traffic_history GROUP BY mode
        ORDER BY peak_ratio - offpeak_ratio DESC""")


def reliability_by_mode() -> pd.DataFrame:
    """Share of trips that ran more than 25 % over schedule (a simple reliability score)."""
    return query_df("""
        SELECT mode, COUNT(*) AS trips,
               ROUND(100.0 * SUM(delay_ratio > 1.25) / COUNT(*), 1) AS pct_trips_over_25pct_late,
               ROUND(AVG(actual_time_min - base_time_min), 1) AS avg_extra_minutes
        FROM traffic_history GROUP BY mode ORDER BY pct_trips_over_25pct_late""")


def mode_rankings() -> pd.DataFrame:
    """Rank every mode on each route by fare and by time (window functions)."""
    return query_df("""
        WITH r AS (SELECT MIN(start, destination) AS a, MAX(start, destination) AS b, transport_mode AS mode,
                          estimated_fare_inr AS fare, estimated_time_min AS minutes
                   FROM transport_routes)
        SELECT a || ' - ' || b AS route, mode, fare, minutes,
               RANK() OVER (PARTITION BY a, b ORDER BY fare)    AS fare_rank,
               RANK() OVER (PARTITION BY a, b ORDER BY minutes) AS time_rank,
               COUNT(*) OVER (PARTITION BY a, b)                AS options
        FROM r ORDER BY route, fare_rank""")


def best_value_modes() -> pd.DataFrame:
    """For routes with 2+ options: which mode wins on fare and which on time most often."""
    return query_df("""
        WITH r AS (SELECT MIN(start, destination) AS a, MAX(start, destination) AS b, transport_mode AS mode,
                          estimated_fare_inr AS fare, estimated_time_min AS minutes FROM transport_routes),
        ranked AS (SELECT mode,
                          RANK() OVER (PARTITION BY a, b ORDER BY fare)    AS fr,
                          RANK() OVER (PARTITION BY a, b ORDER BY minutes) AS tr,
                          COUNT(*) OVER (PARTITION BY a, b)                AS n FROM r)
        SELECT mode, SUM(fr = 1) AS cheapest_on_routes, SUM(tr = 1) AS fastest_on_routes, COUNT(*) AS routes_served
        FROM ranked WHERE n >= 2 GROUP BY mode ORDER BY cheapest_on_routes DESC, fastest_on_routes DESC""")


def popular_routes(limit: int = 10) -> pd.DataFrame:
    return query_df("""
        SELECT start, destination, COUNT(*) AS searches, ROUND(AVG(total_fare_inr), 1) AS avg_fare,
               ROUND(AVG(total_time_min), 1) AS avg_minutes
        FROM journey_logs GROUP BY start, destination ORDER BY searches DESC LIMIT ?""", (limit,))


def searches_by_day() -> pd.DataFrame:
    return query_df("SELECT date(created_at) AS day, COUNT(*) AS searches FROM journey_logs GROUP BY day ORDER BY day")


def feedback_summary() -> pd.DataFrame:
    return query_df("""
        SELECT j.priority, COUNT(f.id) AS ratings, ROUND(AVG(f.rating), 2) AS avg_rating
        FROM feedback f LEFT JOIN journey_logs j ON j.id = f.journey_id GROUP BY j.priority""")


def overview() -> dict:
    from db.database import table_counts
    return table_counts()
