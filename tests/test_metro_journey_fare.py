import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

FARE_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cmrl_metro_fares.csv"
)

df = pd.read_csv(FARE_FILE)

start = "Egmore"
destination = "Airport"

fare = df[
    (df["start"] == start)
    & (df["destination"] == destination)
]

print("\n========== MULTI-STATION METRO FARE TEST ==========")

if fare.empty:
    fare = df[
        (df["start"] == destination)
        & (df["destination"] == start)
    ]

if fare.empty:
    raise ValueError("Direct CMRL fare not found!")

row = fare.iloc[0]

print("Journey:", start, "->", destination)
print("Regular fare: Rs.", row["regular_fare"])
print("Discounted fare: Rs.", row["discounted_fare"])

print("\nPASS: Direct journey fare found in CMRL matrix.")