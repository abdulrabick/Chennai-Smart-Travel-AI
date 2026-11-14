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

print("\nMETRO STATION DATA DIAGNOSTICS")
print("=" * 45)

print("\n1. OSM TAG COUNTS")

for column in [
    "osm_type",
    "railway",
    "station",
    "public_transport",
    "subway"
]:
    print(f"\n{column}:")
    print(df[column].value_counts(dropna=False).to_string())


print("\n2. DUPLICATE STATION RECORDS")
print("=" * 45)

duplicates = df[
    df.duplicated("station_name", keep=False)
].sort_values("station_name")

if duplicates.empty:
    print("No duplicate station names.")
else:
    print(
        duplicates[
            [
                "station_name",
                "latitude",
                "longitude",
                "osm_type",
                "osm_id",
                "railway",
                "station",
                "public_transport",
                "subway"
            ]
        ].to_string(index=False)
    )


print("\n3. ALL STATION TAGS")
print("=" * 45)

print(
    df[
        [
            "station_name",
            "osm_type",
            "railway",
            "station",
            "public_transport",
            "subway"
        ]
    ].to_string(index=False)
)

print("\nDIAGNOSTICS COMPLETE")