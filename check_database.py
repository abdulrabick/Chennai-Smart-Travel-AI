import sqlite3

# Connect to database
connection = sqlite3.connect("chennai_travel.db")

# Create cursor
cursor = connection.cursor()

# 1. Total records
cursor.execute("SELECT COUNT(*) FROM transport_routes")
print("Total records:", cursor.fetchone()[0])

# 2. Routes by transport mode
print("\nRoutes by transport mode:")

cursor.execute("""
SELECT transport_mode, COUNT(*)
FROM transport_routes
GROUP BY transport_mode
""")

for row in cursor.fetchall():
    print(row)

# 3. Average fare
print("\nAverage fare by transport mode:")

cursor.execute("""
SELECT transport_mode, AVG(estimated_fare_inr)
FROM transport_routes
GROUP BY transport_mode
""")

for row in cursor.fetchall():
    print(row)

# Close database
connection.close()