import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

FILE_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "classified_metro_stations.csv"
)

# Official CMRL Phase 2 Stage 1A station list
OFFICIAL_STATIONS = [
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


def normalize_name(name):
    return "".join(str(name).lower().split())


def main():

    df = pd.read_csv(FILE_PATH)

    operational = df[
        df["metro_status"] == "Phase 2 - Operational"
    ]

    actual_names = set(
        normalize_name(name)
        for name in operational["station_name"]
    )

    expected_names = set(
        normalize_name(name)
        for name in OFFICIAL_STATIONS
    )

    print("\nMETRO STATION VALIDATION")
    print("========================")

    print("Official stations:", len(expected_names))
    print("Classified records:", len(operational))

    missing = expected_names - actual_names
    unexpected = actual_names - expected_names

    print("\nMissing stations:")

    if missing:
        print(missing)
    else:
        print("None")

    print("\nUnexpected stations:")

    if unexpected:
        print(unexpected)
    else:
        print("None")

    print("\nDuplicate station names:")

    duplicates = operational[
        operational["station_name"].duplicated(keep=False)
    ]

    if duplicates.empty:
        print("None")
    else:
        print(
            duplicates[
                ["station_name", "osm_id", "latitude", "longitude"]
            ].to_string(index=False)
        )

    if not missing and not unexpected:
        print("\nSUCCESS: Official station names match!")
    else:
        print("\nWARNING: Please review station names.")


if __name__ == "__main__":
    main()