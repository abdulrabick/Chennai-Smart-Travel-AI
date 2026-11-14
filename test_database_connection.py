from transport_engine import load_transport_data

# Load routes from SQLite
routes = load_transport_data()

print("SQLite connection successful!")
print("Total routes loaded:", len(routes))

print("\nTransport modes:")

print(routes["transport_mode"].value_counts())

print("\nFirst five routes:")

print(routes.head())