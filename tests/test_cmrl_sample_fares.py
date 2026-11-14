import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

file_path = BASE_DIR / "data" / "processed" / "cmrl_metro_fares.csv"

df = pd.read_csv(file_path)

test_cases = [
    ("Airport", "Meenambakkam", 10, 8),
    ("Airport", "Guindy", 30, 24),
    ("Meenambakkam", "Guindy", 20, 16),
    ("OTA - Nanganallur Road", "Arignar Anna Alandur Metro", 10, 8),
]

print("\n========== CMRL SAMPLE FARE TEST ==========")

for start, destination, regular, discounted in test_cases:

    result = df[
        (df["start"] == start) &
        (df["destination"] == destination)
    ]

    assert len(result) == 1, f"Route missing: {start} -> {destination}"

    actual_regular = result.iloc[0]["regular_fare"]
    actual_discounted = result.iloc[0]["discounted_fare"]

    assert actual_regular == regular, f"Regular fare mismatch: {start} -> {destination}"
    assert actual_discounted == discounted, f"Discounted fare mismatch: {start} -> {destination}"

    print(f"PASS: {start} -> {destination}")

print("\nALL SAMPLE FARE TESTS PASSED!")