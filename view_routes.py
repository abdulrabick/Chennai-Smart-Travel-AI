import sqlite3

connection = sqlite3.connect("chennai_travel.db")
cursor = connection.cursor()

cursor.execute("""
SELECT * FROM transport_routes
WHERE transport_mode = 'Metro'
""")

routes = cursor.fetchall()

for route in routes:
    print(route)

connection.close()