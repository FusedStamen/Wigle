#!/usr/bin/env python3
r"""
wigle_sort_v4.py - WiGLE CSV merger, country/state splitter, and channel analyzer
                   (streaming, low-memory version of v3)

Usage:
  py wigle_sort_v4.py --input "E:\TECH DATA\wardrive\Wigle Full Downloads" --output "E:\TECH DATA\wardrive\Wigle Sorted"

Same outputs as v3 (master deduped, no-GPS file, per-country and per-US-state CSVs,
channel summaries, readme_stats.md), but it no longer loads everything into memory.

How it stays small:
  Pass 1  streams every input file row by row into a temporary SQLite file on disk,
          keeping one row per MAC + Type (the strongest RSSI wins).
  Pass 2  reads that table back one row at a time, classifies it, and appends it to
          the output files. Only running counters stay in memory.

Memory use stays roughly flat no matter how much data you feed it. Disk use during the
run is about the size of your deduped data (the temp file is deleted at the end).

Differences from v3 (see CHANGELOG.md):
  - Reads .csv, .csv.gz and .zip (containing csvs), not just .csv
  - No pandas dependency (standard library only)
  - Skips anything inside the output folder, so re-runs never ingest their own output
  - "Countries covered" in readme_stats.md no longer counts the "other" bucket
  - Channel numbers in the channel summaries are written as integers (6, not 6.0)
  - Rows in the output files are ordered by MAC, not by RSSI
"""

import argparse
import csv
import gzip
import io
import json
import math
import os
import sqlite3
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# csv fields can be large on malformed rows; raise the limit once
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# -- US State bounding boxes ---------------------------------------------------
US_STATES = {
    "alabama":        dict(lat_min=30.14, lat_max=35.01, lon_min=-88.47, lon_max=-84.89),
    "alaska":         dict(lat_min=54.56, lat_max=71.54, lon_min=-179.99,lon_max=-129.99),
    "arizona":        dict(lat_min=31.33, lat_max=37.00, lon_min=-114.82, lon_max=-109.04),
    "arkansas":       dict(lat_min=33.00, lat_max=36.50, lon_min=-94.62, lon_max=-89.64),
    "california":     dict(lat_min=32.53, lat_max=42.01, lon_min=-124.41, lon_max=-114.13),
    "colorado":       dict(lat_min=36.99, lat_max=41.00, lon_min=-109.05, lon_max=-102.04),
    "connecticut":    dict(lat_min=40.98, lat_max=42.05, lon_min=-73.73, lon_max=-71.79),
    "delaware":       dict(lat_min=38.45, lat_max=39.84, lon_min=-75.79, lon_max=-75.04),
    "florida":        dict(lat_min=24.52, lat_max=31.00, lon_min=-87.63, lon_max=-79.50),  # extended east for barrier islands/coastal GPS
    "georgia":        dict(lat_min=30.36, lat_max=35.00, lon_min=-85.61, lon_max=-80.84),
    "hawaii":         dict(lat_min=18.91, lat_max=22.24, lon_min=-160.25, lon_max=-154.81),
    "idaho":          dict(lat_min=41.99, lat_max=49.00, lon_min=-117.24, lon_max=-111.04),
    "illinois":       dict(lat_min=36.97, lat_max=42.51, lon_min=-91.51, lon_max=-87.02),
    "indiana":        dict(lat_min=37.77, lat_max=41.77, lon_min=-88.10, lon_max=-84.78),
    "iowa":           dict(lat_min=40.38, lat_max=43.50, lon_min=-96.64, lon_max=-90.14),
    "kansas":         dict(lat_min=36.99, lat_max=40.00, lon_min=-102.05, lon_max=-94.59),
    "kentucky":       dict(lat_min=36.50, lat_max=39.15, lon_min=-89.57, lon_max=-81.96),
    "louisiana":      dict(lat_min=28.93, lat_max=33.02, lon_min=-94.04, lon_max=-88.82),
    "maine":          dict(lat_min=43.06, lat_max=47.46, lon_min=-71.08, lon_max=-65.50),  # extended east to catch coastal/NB border GPS
    "maryland":       dict(lat_min=37.91, lat_max=39.72, lon_min=-79.49, lon_max=-75.05),
    "massachusetts":  dict(lat_min=41.24, lat_max=42.89, lon_min=-73.51, lon_max=-69.93),
    "michigan":       dict(lat_min=41.70, lat_max=48.31, lon_min=-90.42, lon_max=-79.50),  # extended east to cover Lake Erie corridor
    "minnesota":      dict(lat_min=43.50, lat_max=49.38, lon_min=-97.24, lon_max=-89.49),
    "mississippi":    dict(lat_min=30.17, lat_max=35.01, lon_min=-91.65, lon_max=-88.10),
    "missouri":       dict(lat_min=35.99, lat_max=40.61, lon_min=-95.77, lon_max=-89.10),
    "montana":        dict(lat_min=44.36, lat_max=49.00, lon_min=-116.05, lon_max=-104.04),
    "nebraska":       dict(lat_min=40.00, lat_max=43.00, lon_min=-104.05, lon_max=-95.31),
    "nevada":         dict(lat_min=35.00, lat_max=42.00, lon_min=-120.00, lon_max=-114.04),
    "new_hampshire":  dict(lat_min=42.70, lat_max=45.31, lon_min=-72.56, lon_max=-70.61),
    "new_jersey":     dict(lat_min=38.93, lat_max=41.36, lon_min=-75.57, lon_max=-73.50),  # extended east for coastal GPS
    "new_mexico":     dict(lat_min=31.33, lat_max=37.00, lon_min=-109.05, lon_max=-103.00),
    "new_york":       dict(lat_min=40.50, lat_max=45.90, lon_min=-79.76, lon_max=-71.50),  # extended east for Long Island coast, north for Lake Erie border
    "north_carolina": dict(lat_min=33.84, lat_max=36.59, lon_min=-84.32, lon_max=-75.00),  # extended east for OBX/coastal GPS
    "north_dakota":   dict(lat_min=45.94, lat_max=49.00, lon_min=-104.05, lon_max=-96.55),
    "ohio":           dict(lat_min=38.40, lat_max=42.33, lon_min=-84.82, lon_max=-80.52),
    "oklahoma":       dict(lat_min=33.62, lat_max=37.00, lon_min=-103.00, lon_max=-94.43),
    "oregon":         dict(lat_min=41.99, lat_max=46.26, lon_min=-124.57, lon_max=-116.46),
    "pennsylvania":   dict(lat_min=39.72, lat_max=42.27, lon_min=-80.52, lon_max=-74.69),
    "rhode_island":   dict(lat_min=41.15, lat_max=42.02, lon_min=-71.86, lon_max=-71.12),
    "south_carolina": dict(lat_min=32.05, lat_max=35.22, lon_min=-83.35, lon_max=-77.90),  # extended east for barrier island/coastal GPS
    "south_dakota":   dict(lat_min=42.48, lat_max=45.95, lon_min=-104.06, lon_max=-96.44),
    "tennessee":      dict(lat_min=34.98, lat_max=36.68, lon_min=-90.31, lon_max=-81.65),
    "texas":          dict(lat_min=25.84, lat_max=36.50, lon_min=-106.65, lon_max=-93.51),
    "utah":           dict(lat_min=36.99, lat_max=42.00, lon_min=-114.05, lon_max=-109.04),
    "vermont":        dict(lat_min=42.73, lat_max=45.02, lon_min=-73.44, lon_max=-71.46),
    "virginia":       dict(lat_min=36.54, lat_max=39.47, lon_min=-83.68, lon_max=-75.24),
    "washington":     dict(lat_min=45.54, lat_max=49.00, lon_min=-124.73, lon_max=-116.92),
    "washington_dc":  dict(lat_min=38.79, lat_max=38.99, lon_min=-77.12, lon_max=-76.91),
    "west_virginia":  dict(lat_min=37.20, lat_max=40.64, lon_min=-82.64, lon_max=-77.72),
    "wisconsin":      dict(lat_min=42.49, lat_max=47.31, lon_min=-92.89, lon_max=-86.25),
    "wyoming":        dict(lat_min=40.99, lat_max=45.01, lon_min=-111.06, lon_max=-104.05),
}

# -- Country bounding boxes ----------------------------------------------------
COUNTRIES = {
    # North America
    "usa":              dict(lat_min=24.0,  lat_max=49.5,  lon_min=-125.0, lon_max=-65.0),
    "canada":           dict(lat_min=41.7,  lat_max=84.0,  lon_min=-141.0, lon_max=-52.0),
    "mexico":           dict(lat_min=14.5,  lat_max=32.7,  lon_min=-117.1, lon_max=-86.7),
    # Europe
    "uk":               dict(lat_min=49.9,  lat_max=60.9,  lon_min=-8.2,   lon_max=1.8),
    "ireland":          dict(lat_min=51.4,  lat_max=55.4,  lon_min=-10.5,  lon_max=-6.0),
    "france":           dict(lat_min=41.3,  lat_max=51.1,  lon_min=-5.1,   lon_max=9.6),
    "germany":          dict(lat_min=47.3,  lat_max=55.1,  lon_min=5.9,    lon_max=15.0),
    "netherlands":      dict(lat_min=50.8,  lat_max=53.6,  lon_min=3.4,    lon_max=7.2),
    "belgium":          dict(lat_min=49.5,  lat_max=51.5,  lon_min=2.5,    lon_max=6.4),
    "switzerland":      dict(lat_min=45.8,  lat_max=47.8,  lon_min=5.9,    lon_max=10.5),
    "austria":          dict(lat_min=46.4,  lat_max=49.0,  lon_min=9.5,    lon_max=17.2),
    "spain":            dict(lat_min=36.0,  lat_max=43.8,  lon_min=-9.3,   lon_max=4.3),
    "portugal":         dict(lat_min=36.9,  lat_max=42.2,  lon_min=-9.5,   lon_max=-6.2),
    "italy":            dict(lat_min=36.6,  lat_max=47.1,  lon_min=6.6,    lon_max=18.5),
    "sweden":           dict(lat_min=55.3,  lat_max=69.1,  lon_min=11.1,   lon_max=24.2),
    "norway":           dict(lat_min=57.9,  lat_max=71.2,  lon_min=4.5,    lon_max=31.1),
    "denmark":          dict(lat_min=54.6,  lat_max=57.8,  lon_min=8.1,    lon_max=15.2),
    "finland":          dict(lat_min=59.7,  lat_max=70.1,  lon_min=20.0,   lon_max=31.6),
    "poland":           dict(lat_min=49.0,  lat_max=54.9,  lon_min=14.1,   lon_max=24.2),
    "czechia":          dict(lat_min=48.6,  lat_max=51.1,  lon_min=12.1,   lon_max=18.9),
    "hungary":          dict(lat_min=45.7,  lat_max=48.6,  lon_min=16.1,   lon_max=22.9),
    "romania":          dict(lat_min=43.6,  lat_max=48.3,  lon_min=20.3,   lon_max=30.0),
    "greece":           dict(lat_min=34.8,  lat_max=42.0,  lon_min=19.4,   lon_max=28.3),
    # Asia
    "india":            dict(lat_min=8.0,   lat_max=37.1,  lon_min=68.1,   lon_max=97.4),
    "china":            dict(lat_min=18.2,  lat_max=53.6,  lon_min=73.6,   lon_max=134.8),
    "japan":            dict(lat_min=24.0,  lat_max=45.7,  lon_min=122.9,  lon_max=145.8),
    "south_korea":      dict(lat_min=33.1,  lat_max=38.6,  lon_min=125.1,  lon_max=129.6),
    "taiwan":           dict(lat_min=21.9,  lat_max=25.3,  lon_min=120.1,  lon_max=122.0),
    "singapore":        dict(lat_min=1.1,   lat_max=1.5,   lon_min=103.6,  lon_max=104.1),
    "thailand":         dict(lat_min=5.6,   lat_max=20.5,  lon_min=97.5,   lon_max=105.7),
    "vietnam":          dict(lat_min=8.6,   lat_max=23.4,  lon_min=102.1,  lon_max=109.5),
    "indonesia":        dict(lat_min=-11.0, lat_max=6.1,   lon_min=95.0,   lon_max=141.1),
    "malaysia":         dict(lat_min=0.9,   lat_max=7.4,   lon_min=99.6,   lon_max=119.3),
    "philippines":      dict(lat_min=4.6,   lat_max=21.1,  lon_min=116.9,  lon_max=126.6),
    "israel":           dict(lat_min=29.5,  lat_max=33.3,  lon_min=34.3,   lon_max=35.9),
    "uae":              dict(lat_min=22.6,  lat_max=26.1,  lon_min=51.6,   lon_max=56.4),
    "saudi_arabia":     dict(lat_min=16.4,  lat_max=32.2,  lon_min=34.6,   lon_max=55.7),
    # Oceania
    "australia":        dict(lat_min=-43.7, lat_max=-10.7, lon_min=113.2,  lon_max=153.6),
    "new_zealand":      dict(lat_min=-47.3, lat_max=-34.4, lon_min=166.4,  lon_max=178.6),
    # South America
    "brazil":           dict(lat_min=-33.8, lat_max=5.3,   lon_min=-73.9,  lon_max=-34.8),
    "argentina":        dict(lat_min=-55.1, lat_max=-21.8, lon_min=-73.6,  lon_max=-53.6),
    "colombia":         dict(lat_min=-4.2,  lat_max=13.4,  lon_min=-79.0,  lon_max=-66.8),
    "chile":            dict(lat_min=-55.9, lat_max=-17.5, lon_min=-75.7,  lon_max=-66.4),
    # Africa
    "south_africa":     dict(lat_min=-34.8, lat_max=-22.1, lon_min=16.5,   lon_max=32.9),
    "nigeria":          dict(lat_min=4.3,   lat_max=13.9,  lon_min=2.7,    lon_max=14.7),
    "kenya":            dict(lat_min=-4.7,  lat_max=4.6,   lon_min=33.9,   lon_max=41.9),
    "egypt":            dict(lat_min=22.0,  lat_max=31.7,  lon_min=25.0,   lon_max=37.1),
}

# -- 5 GHz channel groups ------------------------------------------------------
WIFI_5_UNII1 = set(range(36, 52, 4))     # 36,40,44,48
WIFI_5_UNII2 = set(range(52, 100, 4))    # 52-96
WIFI_5_UNII3 = set(range(100, 150, 4))   # 100-148 (DFS)
WIFI_5_UNII4 = set(range(149, 178, 4))   # 149-177

WIGLE_HEADER = "WigleWifi-1.4,appRelease=2.x,model=SERVER,release=2.50,device=WiGLE SERVER,display=NONE,brand=WiGLE.net\n"


def in_bbox(lat, lon, bbox):
    return (bbox["lat_min"] <= lat <= bbox["lat_max"] and
            bbox["lon_min"] <= lon <= bbox["lon_max"])


def bbox_area(bbox):
    return (bbox["lat_max"] - bbox["lat_min"]) * (bbox["lon_max"] - bbox["lon_min"])


# Smallest box first so small states/countries match before larger overlapping ones
_COUNTRIES_SORTED = sorted(COUNTRIES.items(), key=lambda x: bbox_area(x[1]))
_US_STATES_SORTED = sorted(US_STATES.items(), key=lambda x: bbox_area(x[1]))


def classify_country(lat, lon):
    for name, bbox in _COUNTRIES_SORTED:
        if in_bbox(lat, lon, bbox):
            return name
    return "other"


def classify_us_state(lat, lon):
    for name, bbox in _US_STATES_SORTED:
        if in_bbox(lat, lon, bbox):
            return name
    return "us_other"


def channel_band(ch):
    if ch is None:
        return "unknown"
    if 1 <= ch <= 14:
        return "2.4GHz"
    if 36 <= ch < 178:
        return "5GHz"
    return "unknown"


def channel_group(ch):
    if channel_band(ch) == "unknown":
        return "unknown"
    if 1 <= ch <= 14:
        return f"2.4GHz_ch{ch}"
    if ch in WIFI_5_UNII1:
        return "5GHz_UNII1_36-48"
    if ch in WIFI_5_UNII2:
        return "5GHz_UNII2_52-96"
    if ch in WIFI_5_UNII3:
        return "5GHz_UNII3_100-148"
    if ch in WIFI_5_UNII4:
        return "5GHz_UNII4_149-177"
    return f"5GHz_ch{ch}"


def to_float(s):
    """Parse a number; return None for blank/garbage/NaN."""
    try:
        v = float(s)
    except (ValueError, TypeError):
        return None
    if math.isnan(v):
        return None
    return v


def to_channel(s):
    v = to_float(s)
    if v is None:
        return None
    try:
        return int(v)
    except (OverflowError, ValueError):
        return None


# -- Input handling -----------------------------------------------------------
def find_inputs(root, skip_root):
    """All .csv / .csv.gz / .zip files under root, excluding anything under skip_root."""
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        n = p.name.lower()
        if not (n.endswith(".csv") or n.endswith(".csv.gz") or n.endswith(".gz") or n.endswith(".zip")):
            continue
        try:
            p.resolve().relative_to(skip_root)
            continue  # inside the output folder
        except ValueError:
            pass
        out.append(p)
    return out


def open_text(path):
    """Yield (display_name, text_stream) for every csv-like thing at path."""
    s = path.name.lower()
    if s.endswith(".gz"):
        yield path.name, io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace", newline="")
    elif s.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                ln = n.lower()
                if n.endswith("/") or not (ln.endswith(".csv") or ln.endswith(".csv.gz")):
                    continue
                raw = z.open(n)
                if ln.endswith(".gz"):
                    raw = gzip.open(raw, "rb")
                yield f"{path.name}:{n}", io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
    else:
        yield path.name, open(path, "r", encoding="utf-8", errors="replace", newline="")


# -- Pass 1: stream rows into SQLite -------------------------------------------
UPSERT = (
    "INSERT INTO rows(mac, type, rssi, data) VALUES (?,?,?,?) "
    "ON CONFLICT(mac, type) DO UPDATE SET rssi=excluded.rssi, data=excluded.data "
    "WHERE excluded.rssi > rows.rssi OR (rows.rssi IS NULL AND excluded.rssi IS NOT NULL)"
)


def ingest_stream(name, f, db, state, keep_types):
    """Read one WiGLE CSV stream into the db. Returns number of rows read, or None if skipped."""
    first = f.readline()
    if not first:
        print(f"  SKIP (empty): {name}")
        return None
    header_line = f.readline() if first.startswith("WigleWifi") else first
    try:
        header = [h.strip() for h in next(csv.reader([header_line]))]
    except Exception:
        print(f"  SKIP (bad headers): {name}")
        return None
    idx = {h: i for i, h in enumerate(header)}
    if "MAC" not in idx or "Type" not in idx:
        print(f"  SKIP (bad headers): {name}")
        return None

    # The first valid file defines the canonical column order for all outputs.
    if state["columns"] is None:
        state["columns"] = header
    canon = state["columns"]
    # position in this file for each canonical column (None if the file lacks it)
    pos = [idx.get(c) for c in canon]
    same = (header == canon)
    extra = [h for h in header if h not in canon]
    if extra and not state["warned_extra"]:
        state["warned_extra"] = True
        print(f"  note: {name} has columns not in the first file, they are dropped: {extra[:5]}")

    i_mac, i_type, i_rssi = idx["MAC"], idx["Type"], idx.get("RSSI")
    batch = []
    n = 0
    for row in csv.reader(f):
        if len(row) <= max(i_mac, i_type):
            continue
        typ = row[i_type].strip().upper()
        if typ not in keep_types:
            continue
        rssi = to_float(row[i_rssi]) if (i_rssi is not None and i_rssi < len(row)) else None
        if same:
            data = row
        else:
            data = [row[p] if (p is not None and p < len(row)) else "" for p in pos]
        batch.append((row[i_mac], typ, rssi, json.dumps(data, separators=(",", ":"))))
        n += 1
        if len(batch) >= 50000:
            db.executemany(UPSERT, batch)
            batch = []
    if batch:
        db.executemany(UPSERT, batch)
    return n


# -- Output helpers -------------------------------------------------------------
class Writers:
    """Lazily opened csv writers keyed by path; writes the WiGLE preamble + header on first use."""

    def __init__(self, columns):
        self.columns = columns
        self.files = {}

    def write(self, path, row):
        w = self.files.get(path)
        if w is None:
            fh = open(path, "w", encoding="utf-8", newline="")
            fh.write(WIGLE_HEADER)
            cw = csv.writer(fh)
            cw.writerow(self.columns)
            w = (fh, cw)
            self.files[path] = w
        w[1].writerow(row)

    def close(self):
        for fh, _ in self.files.values():
            fh.close()


def write_channel_summary(counter, out_path):
    """counter: Counter of channel int (or None) for WIFI rows in one region."""
    total = sum(counter.values())
    if total == 0:
        return
    bands = Counter()
    for ch, c in counter.items():
        bands[channel_band(ch)] += c
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("# Channel Distribution Summary\n")
        f.write(f"# Total WiFi records: {total}\n\n")
        w = csv.writer(f)
        w.writerow(["band", "count"])
        for b, c in bands.most_common():
            w.writerow([b, c])
        f.write("\n")
        w.writerow(["channel_int", "band", "channel_group", "count"])
        for ch in sorted(k for k in counter if k is not None):
            w.writerow([ch, channel_band(ch), channel_group(ch), counter[ch]])


def write_readme_stats(out_path, total, type_counts, country_counts, state_counts, files_read, files_found):
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    countries_covered = len([c for c in country_counts if c != "other"])
    lines = [
        "<!-- Generated by wigle_sort_v4.py - do not hand-edit, re-run the script instead -->",
        f"<!-- Last generated: {generated} UTC -->",
        "",
        "## WiGLE Stats",
        "",
        f"- **Total unique records:** {total:,}",
        f"- **Input CSVs processed:** {files_read:,} (of {files_found:,} found)",
        f"- **Countries covered:** {countries_covered:,}",
    ]
    if state_counts:
        lines.append(f"- **US states covered:** {len(state_counts):,}")
    lines += ["", "### Type Breakdown", "", "| Type | Count |", "|---|---:|"]
    for t, c in type_counts.most_common():
        lines.append(f"| {t} | {c:,} |")
    lines += ["", "### Top 15 Countries", "", "| Country | Records |", "|---|---:|"]
    for k, c in country_counts.most_common(15):
        lines.append(f"| {k} | {c:,} |")
    lines.append("")
    if state_counts:
        lines += ["### US States", "", "| State | Records |", "|---|---:|"]
        for k, c in state_counts.most_common():
            lines.append(f"| {k} | {c:,} |")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  Readme stats -> {out_path.name}")


def main():
    ap = argparse.ArgumentParser(description="WiGLE CSV merger, region splitter, and channel analyzer (streaming)")
    ap.add_argument("--input", required=True, help="Root folder containing WiGLE CSVs (searched recursively; .csv, .csv.gz, .zip)")
    ap.add_argument("--output", required=True, help="Output folder for sorted CSVs")
    ap.add_argument("--types", default="WIFI,BLE,BT,GSM,LTE,WCDMA", help="Comma-separated types to include (default: all)")
    ap.add_argument("--no-channel-summaries", action="store_true", help="Skip per-region channel summary CSVs")
    ap.add_argument("--no-readme-stats", action="store_true", help="Skip writing readme_stats.md")
    ap.add_argument("--tmp-dir", default=None,
                    help="Where to put the temporary SQLite file (default: the output folder). "
                         "Point this at a drive with free space about the size of your deduped data.")
    args = ap.parse_args()

    input_root = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    if not input_root.is_dir():
        print(f"Input is not a folder: {input_root}")
        sys.exit(1)

    countries_dir = output_root / "countries"
    states_dir = output_root / "us_states"
    summaries_dir = output_root / "channel_summaries"
    for d in (countries_dir, states_dir, summaries_dir):
        d.mkdir(parents=True, exist_ok=True)

    keep_types = set(t.strip().upper() for t in args.types.split(","))
    tmp_dir = Path(args.tmp_dir).expanduser().resolve() if args.tmp_dir else output_root
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / "_wigle_sort_tmp.sqlite"
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.remove(str(db_path) + suffix)
        except OSError:
            pass

    inputs = find_inputs(input_root, output_root)
    print(f"Found {len(inputs)} input files")
    if not inputs:
        print("Nothing to read. Check your input path.")
        return

    # -- Pass 1: stream into SQLite, dedupe by MAC + Type (strongest RSSI wins) ----
    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA temp_store=FILE")
    db.execute("CREATE TABLE rows(mac TEXT NOT NULL, type TEXT NOT NULL, rssi REAL, data TEXT NOT NULL, "
               "PRIMARY KEY(mac, type)) WITHOUT ROWID")
    state = {"columns": None, "warned_extra": False}
    files_read = 0
    rows_in = 0
    for i, path in enumerate(inputs, 1):
        if i % 25 == 0 or i == 1:
            print(f"  Reading {i}/{len(inputs)}: {path.parent.name}/{path.name}   ({rows_in:,} rows so far)")
        try:
            for name, stream in open_text(path):
                with stream:
                    n = ingest_stream(name, stream, db, state, keep_types)
                if n is not None:
                    files_read += 1
                    rows_in += n
            db.commit()
        except Exception as e:
            print(f"  SKIP (error): {path.name} - {e}")
            db.rollback()

    if state["columns"] is None:
        print("No valid CSVs found. Check your input path.")
        db.close()
        os.remove(db_path)
        return

    columns = state["columns"]
    total = db.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    print(f"\n  Rows read (after type filter): {rows_in:,}")
    print(f"  Unique after dedup:            {total:,}")

    try:
        i_lat = columns.index("CurrentLatitude")
        i_lon = columns.index("CurrentLongitude")
    except ValueError:
        print("Files have no CurrentLatitude/CurrentLongitude columns; cannot classify.")
        db.close()
        os.remove(db_path)
        return
    i_type = columns.index("Type")
    i_chan = columns.index("Channel") if "Channel" in columns else None

    # -- Pass 2: classify and write ------------------------------------------------
    print("\nClassifying and writing...")
    writers = Writers(columns)
    type_counts = Counter()
    country_counts = Counter()
    state_counts = Counter()
    chan_by_region = {}          # region key -> Counter of channel ints for WIFI rows
    no_geo = 0
    master_path = output_root / "wigle_master_deduped.csv"
    nogps_path = output_root / "wigle_no_gps.csv"

    def tally_channel(key, row):
        if i_chan is None or row[i_type].strip().upper() != "WIFI":
            return
        ch = to_channel(row[i_chan]) if i_chan < len(row) else None
        chan_by_region.setdefault(key, Counter())[ch] += 1

    cur = db.execute("SELECT data FROM rows")
    done = 0
    for (data,) in cur:
        row = json.loads(data)
        done += 1
        if done % 500000 == 0:
            print(f"  {done:,}/{total:,}")
        typ = row[i_type].strip().upper()
        type_counts[typ] += 1
        writers.write(master_path, row)

        lat = to_float(row[i_lat]) if i_lat < len(row) else None
        lon = to_float(row[i_lon]) if i_lon < len(row) else None
        if lat is None or lon is None:
            no_geo += 1
            writers.write(nogps_path, row)
            continue

        country = classify_country(lat, lon)
        country_counts[country] += 1
        writers.write(countries_dir / f"wigle_{country}.csv", row)
        tally_channel(("c", country), row)

        if country == "usa":
            st = classify_us_state(lat, lon)
            state_counts[st] += 1
            writers.write(states_dir / f"wigle_us_{st}.csv", row)
            tally_channel(("s", st), row)

    writers.close()
    db.close()
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.remove(str(db_path) + suffix)
        except OSError:
            pass

    if not args.no_channel_summaries:
        for (kind, name), counter in chan_by_region.items():
            fname = f"channels_{name}.csv" if kind == "c" else f"channels_us_{name}.csv"
            write_channel_summary(counter, summaries_dir / fname)
        print(f"  Channel summaries: {len(chan_by_region)} files")

    # -- Summary ---------------------------------------------------------------------
    print(f"\n{'-' * 60}")
    print("Done!")
    print(f"\n  Input files processed : {files_read}")
    print(f"  Total unique records  : {total:,}")
    if no_geo:
        print(f"  No GPS                : {no_geo:,}")
    print("\n  Type breakdown:")
    for t, c in type_counts.most_common():
        print(f"    {t:10s}: {c:>10,}")
    print("\n  Top 15 countries (by record count):")
    for k, c in country_counts.most_common(15):
        print(f"    {k:20s}: {c:>10,}")
    if state_counts:
        print("\n  US states (by record count):")
        for k, c in state_counts.most_common():
            print(f"    {k:20s}: {c:>10,}")

    if not args.no_readme_stats:
        write_readme_stats(output_root / "readme_stats.md", total, type_counts, country_counts,
                           state_counts, files_read, len(inputs))

    print(f"\n  Output folder: {output_root}")


if __name__ == "__main__":
    main()
