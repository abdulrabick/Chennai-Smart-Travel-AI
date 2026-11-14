import pandas as pd

file_path = "data/processed/classified_metro_stations.csv"

df = pd.read_csv(file_path)

print("\n========== METRO STATUS ==========")
print(df["metro_status"].value_counts(dropna=False))

print("\n========== MAP COLOURS ==========")
print(df["map_colour"].value_counts(dropna=False))

print("\n========== ENGLISH STATION NAMES ==========")

english = df[
    ~df["station_name"].astype(str).str.contains(
        r"[\u0B80-\u0BFF]",
        regex=True
    )
]

print(
    english[
        ["station_name", "metro_status", "map_colour"]
    ].to_string(index=False)
)

print("\nTotal English-name records:", len(english))