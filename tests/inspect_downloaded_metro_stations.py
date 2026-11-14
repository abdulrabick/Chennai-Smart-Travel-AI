import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "metro_station_coordinates.csv"
)

df = pd.read_csv(CSV_FILE)

print("\nCHENNAI METRO STATION DATA")
print("==============================")

print("Total records:", len(df))

print("\nStation names and coordinates:")

print(
    df[
        ["station_name", "latitude", "longitude"]
    ].to_string(index=False)
)

print("\nDuplicate station names:")

print(
    df[df.duplicated("station_name", keep=False)]
    ["station_name"]
    .to_list()
)

print("\nMissing values:")

print(df.isnull().sum())

print("\nINSPECTION COMPLETE")