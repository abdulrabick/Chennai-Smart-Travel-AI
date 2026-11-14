import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

FARE_FILE = BASE_DIR / "data" / "processed" / "cmrl_metro_fares.csv"

# Load Metro fare data
df = pd.read_csv(FARE_FILE)

print("\n========== CMRL FARE VALIDATION ==========")

# 1. Check columns
required_columns = [
    "start",
    "destination",
    "regular_fare",
    "discounted_fare"
]

assert all(column in df.columns for column in required_columns)
print("PASS: Required columns exist")

# 2. Check total records
assert len(df) == 2550
print("PASS: 2550 fare records found")

# 3. Check missing values
assert not df[required_columns].isnull().any().any()
print("PASS: No missing values")

# 4. Check duplicate routes
assert not df.duplicated(
    subset=["start", "destination"]
).any()
print("PASS: No duplicate routes")

# 5. Check discounted fares
assert (
    df["discounted_fare"] <= df["regular_fare"]
).all()
print("PASS: Discounted fares are valid")

# 6. Check a known fare
fare = df[
    (df["start"] == "Airport") &
    (df["destination"] == "Guindy")
]

assert len(fare) == 1
assert fare.iloc[0]["regular_fare"] == 30
assert fare.iloc[0]["discounted_fare"] == 24

print("PASS: Airport -> Guindy fare verified")

print("\nALL BASIC TESTS PASSED!")