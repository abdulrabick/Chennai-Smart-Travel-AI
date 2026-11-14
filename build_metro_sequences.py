import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

FARE_FILE = BASE_DIR / "data" / "processed" / "cmrl_metro_fares.csv"

OUTPUT_FILE = BASE_DIR / "data" / "processed" / "metro_line_sequences.csv"


# ==========================================
# BLUE LINE
# Airport -> Wimco Nagar
# ==========================================

blue_line = [
    "Airport",
    "Meenambakkam",
    "OTA - Nanganallur Road",
    "Arignar Anna Alandur Metro",
    "Guindy",
    "Little Mount",
    "Saidapet",
    "Nandanam",
    "Teynampet",
    "AG-DMS",
    "Thousand Lights",
    "LIC",
    "Government Estate",
    "Central Metro",
    "High Court",
    "Mannadi",
    "Washermanpet",
    "Thyagaraya College",
    "Tondiarpet",
    "New Washermenpet",
    "Tollgate",
    "Kaladipet",
    "Thiruvottriyur Theradi",
    "Thiruvottriyur",
    "Wimconagar",
]


# ==========================================
# GREEN LINE
# Central -> St Thomas Mount
# ==========================================

green_line = [
    "Central Metro",
    "Egmore",
    "Nehru Park",
    "Kilpauk",
    "Pachiappas College",
    "Shenoy Nagar",
    "Anna Nagar East",
    "Anna Nagar Tower",
    "Thirumangalam",
    "Koyambedu",
    "CMBT Metro",
    "Arumbakkam",
    "Vadapalani",
    "Ashok Nagar",
    "Ekkattuthangal",
    "Arignar Anna Alandur Metro",
    "St Thomas Mount",
]


# ==========================================
# YELLOW LINE
# Poonamallee Bypass -> Vadapalani
# ==========================================

yellow_line = [
    "Poonamallee Bypass",
    "Poonamallee Bus Stand",
    "Poonamallee Government Hospital",
    "Karayanchavadi",
    "Kumananchavadi",
    "Kattupakkam",
    "Iyappanthangal",
    "Thelliyaragaram",
    "Porur Bypass",
    "Porur Junction",
    "Vadapalani",
]


# ==========================================
# CREATE COMBINED DATASET
# ==========================================

records = []

metro_lines = {
    "Blue Line": blue_line,
    "Green Line": green_line,
    "Yellow Line": yellow_line,
}

for line_name, stations in metro_lines.items():

    for sequence, station in enumerate(stations, start=1):

        records.append({
            "station_name": station,
            "line_name": line_name,
            "sequence": sequence,
            "direction": "Both",
        })


df = pd.DataFrame(records)


# ==========================================
# VALIDATE STATION NAMES AGAINST FARE CSV
# ==========================================

fare_df = pd.read_csv(FARE_FILE)

fare_stations = set(fare_df["start"].str.strip())
fare_stations.update(fare_df["destination"].str.strip())

missing_stations = sorted(
    set(df["station_name"]) - fare_stations
)

print("\n========== METRO SEQUENCE VALIDATION ==========")

print("Blue Line:", len(blue_line), "stations")
print("Green Line:", len(green_line), "stations")
print("Yellow Line:", len(yellow_line), "stations")

print("Total sequence records:", len(df))
print("Unique stations:", df["station_name"].nunique())

if missing_stations:

    print("\nERROR: These stations are missing from CMRL fare data:")

    for station in missing_stations:
        print("-", station)

    raise ValueError("Metro station name validation failed.")

print("\nPASS: Every sequence station exists in CMRL fare data.")


# ==========================================
# SAVE FILE
# ==========================================

df.to_csv(OUTPUT_FILE, index=False)

print("\nFile created successfully:")
print(OUTPUT_FILE)

print("\n========== LINE SUMMARY ==========")

print(
    df.groupby("line_name")["station_name"]
    .count()
)

print("\nMETRO SEQUENCE BUILD COMPLETED!")