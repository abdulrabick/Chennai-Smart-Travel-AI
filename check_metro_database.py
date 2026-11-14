import sqlite3

connection = sqlite3.connect("chennai_travel.db")

query = """
SELECT
    start,
    destination,
    transport_mode,
    distance_km,
    estimated_time_min,
    estimated_fare_inr
FROM transport_routes
WHERE transport_mode = 'Metro'
"""

rows = connection.execute(query).fetchall()

print("\n========== EXISTING METRO CONNECTIONS ==========\n")

for row in rows:
    print(row)

print(f"\nTotal Metro records: {len(rows)}")

connection.close()