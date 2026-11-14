import sqlite3

# Connect to database
connection = sqlite3.connect("chennai_travel.db")

# Create cursor
cursor = connection.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS transport_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT NOT NULL,
    destination TEXT NOT NULL,
    transport_mode TEXT NOT NULL,
    distance_km REAL,
    estimated_time_min REAL,
    estimated_fare_inr REAL
)
""")
cursor.execute("""
INSERT INTO transport_routes
(start, destination, transport_mode, distance_km,
 estimated_time_min, estimated_fare_inr)
VALUES (?, ?, ?, ?, ?, ?)
""", ("Egmore", "Guindy", "Metro", 9.0, 18, 40))
# Save changes
connection.commit()

# Close connection
connection.close()

print("Transport routes table created successfully!")