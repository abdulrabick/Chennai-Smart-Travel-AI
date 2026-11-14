import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "metro_station_coordinates.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "classified_metro_stations.csv"
)

df = pd.read_csv(INPUT_FILE)

# Phase 1 operational stations
PHASE_1 = {
    "Alandur",
    "St. Thomas Mount Metro",
    "Ekkattuthangal",
    "Ashok Nagar",
    "Vadapalani",
    "Arumbakkam",
    "CMBT",
    "Koyambedu",
    "Pachaiyappa's College",
    "Kilpauk",
    "Nehru Park",
    "Egmore",
    "ஆயிரம் விளக்கு",
    "எல் ஐ சி",
    "அரசினர் தோட்டம்",
    "High Court",
    "Mannadi",
    "Washermanpet",
    "Nanganallur Road",
    "Meenambakkam",
    "Chennai International Airport",
    "தேனாம்பேட்டை",
    "நந்தனம்",
    "சைதாப்பேட்டை",
    "சின்னமலை",
    "கிண்டி",
    "ஏ ஜி டி.எம்.எஸ்",
    "Central Metro",
    "Sir Theagaraya College",
    "Tondiarpet",
    "Wimco Nagar",
    "Thiruvottriyur",
    "Kaladipet",
    "சுங்கச்சாவடி",
    "புது வண்ணாரப்பேட்டை",
    "Thiruvottiyur Theradi",
    "Shenoy Nagar Metro",
    "Anna Nagar East",
    "Anna Nagar Tower",
    "Thirumangalam",
}

# Phase 2 stations
PHASE_2 = {
    "Porur Junction",
    "Poonamallee Bypass",
    "Thelliyaragaram",
    "Porur Bypass",
    "Kumananchavadi",
    "Poonamallee Government Hospital",
    "Poonamallee Bus Stand",
    "Kattupakkam",
    "Karayanchavadi",
    "Iyappanthangal",
    "Madhavaram Milk Colony",
    "Sholinganallur Metro",
    "Kodambakkam Metro",
    "Panagal Park Metro",
    "Boat Club Metro",
    "Bharathidasan Road Metro",
    "Alwarpet Metro",
    "Thirumayilai Metro",
    "Kutchery Road Metro",
    "Lighthouse Metro",
    "Royapettah Metro",
    "Kodambakkam Powerhouse",
    "Alwarthirunagar",
    "Valasaravakkam",
    "Karambakkam",
    "Alapakkam",
    "Virugambakkam South",
    "Saligramam",
    "Virugambakkam North",
    "Natesan Nagar",
    "Koyambedu Market",
    "Madhavaram Bus Terminal Metro",
    "Assissi Nagar",
    "Manjampakkam",
    "Velmurugan Nagar",
    "Shastri Nagar",
    "Retteri Junction Metro",
    "Kolathur",
    "Srinivasa Nagar",
    "Villivakkam Metro",
    "Mugalivakkam",
    "Ramapuram",
    "Manapakkam",
    "Chennai Trade Centre",
    "Butt Road",
    "Villivakkam Bus Terminus Metro",
    "Anna Nagar West",
    "Thirumangalam Junction",
    "Villivakkam CTH Road",
    "Anna Nagar KV",
}

# Phase 2 Corridor 4 operational stations
PHASE_2_OPERATIONAL = {
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
}

DEPOTS = {
    "Wimco Nagar Depot",
    "Madhavaram Depot",
}


def classify_station(name, osm_id):

    # Vadapalani has two OSM records.
    # This ID assignment is provisional and requires
    # verification against the actual Metro geometry.
    if name == "Vadapalani":
        if str(osm_id) == "14240033431":
            return "Phase 2 - Operational"

        return "Phase 1 - Operational"

    if name in PHASE_2_OPERATIONAL:
        return "Phase 2 - Operational"

    if name in PHASE_1:
        return "Phase 1 - Operational"

    if name in PHASE_2:
        return "Phase 2 - Planned / Construction"

    if name in DEPOTS:
        return "Depot / Non-passenger Facility"

    return "Needs Verification"


# Classify every station
df["metro_status"] = df.apply(
    lambda row: classify_station(
        row["station_name"],
        row["osm_id"]
    ),
    axis=1
)

# Assign map colours
df["map_colour"] = df["metro_status"].map({
    "Phase 1 - Operational": "blue",
    "Phase 2 - Operational": "green",
    "Phase 2 - Planned / Construction": "orange",
    "Depot / Non-passenger Facility": "purple",
    "Needs Verification": "grey",
})

# Preserve duplicate records for investigation
df["duplicate_name"] = df.duplicated(
    subset=["station_name"],
    keep=False
)

# Save classified dataset
df.to_csv(OUTPUT_FILE, index=False)


# Display results
print("\nCHENNAI METRO STATION CLASSIFICATION")
print("=" * 45)

print("\nCategory counts:")
print(df["metro_status"].value_counts())

print("\nDuplicate station records:")

print(
    df[df["duplicate_name"]][
        [
            "station_name",
            "osm_id",
            "latitude",
            "longitude",
            "metro_status",
        ]
    ].to_string(index=False)
)

print("\nPhase 1 operational stations:")
print(
    df[df["metro_status"] == "Phase 1 - Operational"]
    ["station_name"].to_list()
)

print("\nPhase 2 operational stations:")
print(
    df[df["metro_status"] == "Phase 2 - Operational"]
    ["station_name"].to_list()
)

print("\nPhase 2 planned / construction stations:")
print(
    df[df["metro_status"] == "Phase 2 - Planned / Construction"]
    ["station_name"].to_list()
)

print("\nUnverified stations:")
print(
    df[df["metro_status"] == "Needs Verification"]
    ["station_name"].to_list()
)

print("\nSaved file:")
print(OUTPUT_FILE)

print("\nCLASSIFICATION COMPLETE")