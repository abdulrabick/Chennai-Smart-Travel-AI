"""Build the documents the assistant can search (RAG knowledge base).

1. Documents generated from the project's own data (metro network, fares, modes, places, how the system works).
   Everything in them is computed from the CSV/SQLite files, nothing is typed in from memory.
2. Any .md / .txt / .pdf you drop into data/knowledge/ (e.g. official CMRL, MTC or Southern Railway notices).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import settings
from ml.traffic_data import MODE_PARAMS, RAIN_PROB_BY_MONTH


@dataclass
class Document:
    source: str
    title: str
    text: str


def _metro_network_doc() -> Document:
    seq = pd.read_csv(settings.PROCESSED_DIR / "metro_line_sequences.csv")
    lines = []
    for line, grp in seq.sort_values("sequence").groupby("line_name", sort=False):
        names = grp["station_name"].tolist()
        lines.append(f"{line} has {len(names)} stations in this dataset, running from {names[0]} to {names[-1]}. "
                     f"Stations in order: {', '.join(names)}.")
    counts = seq.groupby("station_name")["line_name"].nunique()
    interchanges = sorted(counts[counts > 1].index)
    lines.append("Interchange stations (served by more than one metro line): " +
                 (", ".join(interchanges) if interchanges else "none found in the dataset") + ".")
    return Document("generated/metro_network", "Chennai Metro network (project dataset)", "\n\n".join(lines))


def _metro_fare_doc() -> Document:
    fares = pd.read_csv(settings.PROCESSED_DIR / "cmrl_metro_fares.csv")
    slabs = sorted(fares["regular_fare"].unique())
    ratio = (fares["discounted_fare"] / fares["regular_fare"]).round(2).mode().iloc[0]
    sample = fares.sample(6, random_state=1)
    ex = "; ".join(f"{r.start} to {r.destination}: regular Rs.{r.regular_fare:.0f}, discounted Rs.{r.discounted_fare:.0f}"
                   for r in sample.itertuples())
    text = (f"The metro fare table has {len(fares)} station pairs. Regular fares range from Rs.{fares['regular_fare'].min():.0f} "
            f"to Rs.{fares['regular_fare'].max():.0f}. Fare slabs used: {', '.join(f'Rs.{s:.0f}' for s in slabs)}.\n\n"
            f"The discounted fare is typically {ratio:.0%} of the regular fare (the app labels it 20% discounted fare, "
            f"subject to CMRL eligibility and terms).\n\nExample fares from the table: {ex}.\n\n"
            "Metro fare is charged on the direct origin-to-destination fare, not per station.")
    return Document("generated/metro_fares", "Chennai Metro fares (project dataset)", text)


def _modes_doc() -> Document:
    from db.database import query_df
    summ = query_df("SELECT * FROM v_mode_summary ORDER BY fare_per_km")
    parts = []
    for r in summ.itertuples():
        sens = MODE_PARAMS.get(r.transport_mode)
        parts.append(f"{r.transport_mode}: {r.options} route options in the dataset, average fare Rs.{r.avg_fare_inr}, "
                     f"average time {r.avg_time_min} min over {r.avg_distance_km} km (about Rs.{r.fare_per_km} per km, "
                     f"average speed {r.avg_speed_kmph} km/h)."
                     + (f" Modelled traffic sensitivity: rush-hour +{sens['peak']:.0%}, heavy rain +{sens['rain']:.0%}." if sens else ""))
    parts.append("Cheapest per kilometre in this dataset is "
                 f"{summ.iloc[0].transport_mode}; metro and local train are least affected by road traffic because they run on "
                 "dedicated tracks, while buses, autos, bike taxis and cabs slow down most in rush hour and rain.")
    return Document("generated/modes", "Transport modes compared (project dataset)", "\n\n".join(parts))


def _places_doc() -> Document:
    from db.database import query_df
    d = query_df("""SELECT start AS a, destination AS b, transport_mode AS mode FROM transport_routes""")
    places = sorted(set(d["a"]) | set(d["b"]))
    lines = [f"The non-metro route dataset covers these places: {', '.join(places)}."]
    for p in places:
        sub = d[(d["a"] == p) | (d["b"] == p)]
        nbrs = sorted(set(sub["a"]) | set(sub["b"]) - {p} - {p})
        nbrs = [n for n in nbrs if n != p]
        lines.append(f"{p} connects directly to {', '.join(nbrs)} using {', '.join(sorted(set(sub['mode'])))}.")
    return Document("generated/places", "Places and direct connections (project dataset)", "\n\n".join(lines))


def _how_it_works_doc() -> Document:
    peak = "weekday mornings around 9 am and evenings around 6-7 pm"
    wet = ", ".join(str(m) for m, p in RAIN_PROB_BY_MONTH.items() if p >= 0.3)
    text = (
        "How routes are chosen: the app builds a graph of places and metro stations. Each connection has a time, fare and distance. "
        "Fastest minimises time plus transfer time, Cheapest minimises fare, Shortest minimises distance.\n\n"
        "Traffic-aware routing: a machine-learning model predicts a delay ratio (actual time divided by scheduled time) from the transport "
        f"mode, hour, weekday, month and rain level. Rush hours in the model are {peak}. Months with the highest modelled rain chance "
        f"(north-east monsoon) are month numbers {wet}. A ratio of 1.30 means the journey takes 30 percent longer than scheduled.\n\n"
        "Important limits: fares, times and delays are prototype estimates from the project dataset and a simulated traffic history. "
        "They are not live fares, live timings or live traffic. Always check official CMRL, MTC and Southern Railway sources before travelling."
    )
    return Document("generated/how_it_works", "How Chennai Smart Travel AI works", text)


def _user_documents() -> list[Document]:
    docs = []
    if not settings.KNOWLEDGE_DIR.exists():
        return docs
    for p in sorted(settings.KNOWLEDGE_DIR.iterdir()):
        try:
            if p.suffix.lower() in (".md", ".txt"):
                text = p.read_text(encoding="utf-8", errors="ignore")
            elif p.suffix.lower() == ".pdf":
                import pdfplumber
                with pdfplumber.open(p) as pdf:
                    text = "\n\n".join((pg.extract_text() or "") for pg in pdf.pages)
            else:
                continue
        except Exception as exc:
            print(f"[knowledge_base] skipped {p.name}: {exc}")
            continue
        if text.strip():
            docs.append(Document(f"knowledge/{p.name}", p.stem.replace("_", " "), text))
    return docs


def build_documents() -> list[Document]:
    docs = []
    for fn in (_metro_network_doc, _metro_fare_doc, _modes_doc, _places_doc, _how_it_works_doc):
        try:
            docs.append(fn())
        except Exception as exc:        # e.g. database not initialised yet
            print(f"[knowledge_base] {fn.__name__} skipped: {exc}")
    return docs + _user_documents()
