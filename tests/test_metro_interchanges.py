import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

FILE = BASE_DIR / "data" / "processed" / "metro_line_sequences.csv"

df = pd.read_csv(FILE)

expected_interchanges = {
    "Central Metro": {"Blue Line", "Green Line"},
    "Arignar Anna Alandur Metro": {"Blue Line", "Green Line"},
    "Vadapalani": {"Green Line", "Yellow Line"},
}

print("\n========== METRO INTERCHANGE TEST ==========\n")

for station, expected_lines in expected_interchanges.items():

    actual_lines = set(
        df.loc[
            df["station_name"] == station,
            "line_name"
        ]
    )

    print(f"{station}: {actual_lines}")

    assert actual_lines == expected_lines, (
        f"Incorrect interchange: {station}"
    )

    print(f"PASS: {station}\n")

print("ALL INTERCHANGE TESTS PASSED!")