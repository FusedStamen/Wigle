#!/usr/bin/env python3
"""
wigle_sort.py — WiGLE CSV merger, country/state splitter, and channel analyzer
Usage: python wigle_sort.py --input "E:\\TECH DATA\\wardrive\\Wigle Full Downloads" --output "E:\\TECH DATA\\wardrive\\Wigle Sorted"

Merges all WiGLE CSVs across month folders, deduplicates by MAC+Type,
splits into country and US state files, and generates channel summary reports.
"""

import argparse
import pandas as pd
from pathlib import Path

# ── US State bounding boxes ───────────────────────────────────────────────────
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

# ── Country bounding boxes ────────────────────────────────────────────────────
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

# ── 2.4 GHz channel center frequencies (MHz) ─────────────────────────────────
WIFI_24_CHANNELS = {
    1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432,
    6: 2437, 7: 2442, 8: 2447, 9: 2452, 10: 2457,
    11: 2462, 12: 2467, 13: 2472, 14: 2484,
}

# ── 5 GHz channel groups ──────────────────────────────────────────────────────
WIFI_5_UNII1  = list(range(36, 52, 4))    # 36,40,44,48  — UNII-1
WIFI_5_UNII2  = list(range(52, 100, 4))   # 52–96        — UNII-2A/2C
WIFI_5_UNII3  = list(range(100, 150, 4))  # 100–148      — UNII-3 (DFS)
WIFI_5_UNII4  = list(range(149, 178, 4))  # 149–177      — UNII-3 upper


def in_bbox(lat, lon, bbox):
    return (bbox["lat_min"] <= lat <= bbox["lat_max"] and
            bbox["lon_min"] <= lon <= bbox["lon_max"])


def classify_country(lat, lon):
    for name, bbox in COUNTRIES.items():
        if in_bbox(lat, lon, bbox):
            return name
    return "other"


def classify_us_state(lat, lon):
    for name, bbox in US_STATES.items():
        if in_bbox(lat, lon, bbox):
            return name
    return "us_other"


def channel_band(ch):
    """Return '2.4GHz' or '5GHz' or 'unknown' for a channel number."""
    try:
        ch = int(float(ch))
    except (ValueError, TypeError):
        return "unknown"
    if 1 <= ch <= 14:
        return "2.4GHz"
    if ch in range(36, 178):
        return "5GHz"
    return "unknown"


def channel_group(ch):
    """Return a descriptive group for a channel number."""
    try:
        ch = int(float(ch))
    except (ValueError, TypeError):
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


def read_wigle_csv(path):
    """Read a WiGLE CSV, skipping the metadata header line."""
    try:
        df = pd.read_csv(path, skiprows=1, low_memory=False, encoding="utf-8", encoding_errors="replace")
        if "MAC" not in df.columns or "Type" not in df.columns:
            print(f"  SKIP (bad headers): {path.name}")
            return None
        return df
    except Exception as e:
        print(f"  SKIP (error): {path.name} — {e}")
        return None


def write_csv(df, path, wigle_header):
    """Write a dataframe to a WiGLE-compatible CSV."""
    if df.empty:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(wigle_header)
    df.to_csv(path, mode="a", index=False)


def write_channel_summary(df, out_path):
    """Write a channel distribution summary CSV for a region."""
    if df.empty or "Channel" not in df.columns:
        return

    wifi = df[df["Type"] == "WIFI"].copy()
    if wifi.empty:
        return

    wifi["channel_int"] = pd.to_numeric(wifi["Channel"], errors="coerce")
    wifi["band"] = wifi["channel_int"].apply(channel_band)
    wifi["channel_group"] = wifi["channel_int"].apply(channel_group)

    # Per-channel count
    ch_counts = (
        wifi.groupby(["channel_int", "band", "channel_group"])
        .size()
        .reset_index(name="count")
        .sort_values("channel_int")
    )

    # Band summary
    band_counts = wifi["band"].value_counts().reset_index()
    band_counts.columns = ["band", "count"]

    # Write
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Channel Distribution Summary\n")
        f.write(f"# Total WiFi records: {len(wifi)}\n\n")

    band_counts.to_csv(out_path, mode="a", index=False)
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("\n")
    ch_counts.to_csv(out_path, mode="a", index=False)

    print(f"    Channel summary → {out_path.name}")


def main():
    parser = argparse.ArgumentParser(description="WiGLE CSV merger, region splitter, and channel analyzer")
    parser.add_argument("--input",   required=True, help="Root folder containing month subfolders with WiGLE CSVs")
    parser.add_argument("--output",  required=True, help="Output folder for sorted CSVs")
    parser.add_argument("--types",   default="WIFI,BLE,BT,GSM,LTE,WCDMA",
                        help="Comma-separated types to include (default: all)")
    parser.add_argument("--no-channel-summaries", action="store_true",
                        help="Skip writing per-region channel summary CSVs")
    args = parser.parse_args()

    input_root  = Path(args.input)
    output_root = Path(args.output)
    channel_summaries = not args.no_channel_summaries

    # Create output directory structure
    countries_dir = output_root / "countries"
    states_dir    = output_root / "us_states"
    summaries_dir = output_root / "channel_summaries"
    for d in [countries_dir, states_dir, summaries_dir]:
        d.mkdir(parents=True, exist_ok=True)

    keep_types = set(t.strip().upper() for t in args.types.split(","))

    wigle_header = "WigleWifi-1.4,appRelease=2.x,model=SERVER,release=2.50,device=WiGLE SERVER,display=NONE,brand=WiGLE.net\n"

    # ── Step 1: Find all CSVs ─────────────────────────────────────────────────
    csv_files = sorted(input_root.rglob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")

    # ── Step 2: Read and merge ────────────────────────────────────────────────
    frames = []
    for i, path in enumerate(csv_files, 1):
        if i % 50 == 0 or i == 1:
            print(f"  Reading {i}/{len(csv_files)}: {path.parent.name}/{path.name}")
        df = read_wigle_csv(path)
        if df is not None:
            frames.append(df)

    if not frames:
        print("No valid CSVs found. Check your input path.")
        return

    print(f"\nMerging {len(frames)} files...")
    master = pd.concat(frames, ignore_index=True)
    print(f"  Total rows before dedup: {len(master):,}")

    # ── Step 3: Filter types ──────────────────────────────────────────────────
    master["Type"] = master["Type"].astype(str).str.upper().str.strip()
    master = master[master["Type"].isin(keep_types)]
    print(f"  Rows after type filter:  {len(master):,}")

    # ── Step 4: Deduplicate by MAC + Type, keep strongest RSSI ───────────────
    master["RSSI"] = pd.to_numeric(master["RSSI"], errors="coerce")
    master = master.sort_values("RSSI", ascending=False)
    master = master.drop_duplicates(subset=["MAC", "Type"], keep="first")
    print(f"  Rows after dedup:        {len(master):,}")

    # ── Step 5: Parse coordinates ─────────────────────────────────────────────
    master["CurrentLatitude"]  = pd.to_numeric(master["CurrentLatitude"],  errors="coerce")
    master["CurrentLongitude"] = pd.to_numeric(master["CurrentLongitude"], errors="coerce")

    has_geo = master.dropna(subset=["CurrentLatitude", "CurrentLongitude"]).copy()
    no_geo  = master[master["CurrentLatitude"].isna() | master["CurrentLongitude"].isna()].copy()

    print(f"\nClassifying {len(has_geo):,} geolocated records ({len(no_geo):,} have no GPS)...")

    # ── Step 6: Country classification ───────────────────────────────────────
    has_geo["country"] = has_geo.apply(
        lambda r: classify_country(r["CurrentLatitude"], r["CurrentLongitude"]), axis=1
    )

    # ── Step 7: US state classification ──────────────────────────────────────
    us_records = has_geo[has_geo["country"] == "usa"].copy()
    if not us_records.empty:
        print(f"  Classifying {len(us_records):,} US records by state...")
        us_records["state"] = us_records.apply(
            lambda r: classify_us_state(r["CurrentLatitude"], r["CurrentLongitude"]), axis=1
        )

    # ── Step 8: Write master deduped file ─────────────────────────────────────
    master_out = output_root / "wigle_master_deduped.csv"
    write_csv(master.drop(columns=["country", "state"], errors="ignore"), master_out, wigle_header)
    print(f"\n  Master deduped: {len(master):,} records → wigle_master_deduped.csv")

    # ── Step 9: Write no-GPS file ─────────────────────────────────────────────
    if not no_geo.empty:
        write_csv(no_geo, output_root / "wigle_no_gps.csv", wigle_header)
        print(f"  No GPS: {len(no_geo):,} records → wigle_no_gps.csv")

    # ── Step 10: Write country files ──────────────────────────────────────────
    print(f"\nWriting country files to {countries_dir}...")
    country_counts = has_geo["country"].value_counts()

    for country in sorted(has_geo["country"].unique()):
        subset = has_geo[has_geo["country"] == country].drop(columns=["country", "state"], errors="ignore")
        out_path = countries_dir / f"wigle_{country}.csv"
        write_csv(subset, out_path, wigle_header)
        print(f"  {country:20s}: {len(subset):>8,} records")

        if channel_summaries:
            write_channel_summary(subset, summaries_dir / f"channels_{country}.csv")

    # ── Step 11: Write US state files ─────────────────────────────────────────
    if not us_records.empty:
        print(f"\nWriting US state files to {states_dir}...")
        for state in sorted(us_records["state"].unique()):
            subset = us_records[us_records["state"] == state].drop(columns=["country", "state"], errors="ignore")
            out_path = states_dir / f"wigle_us_{state}.csv"
            write_csv(subset, out_path, wigle_header)
            print(f"  {state:20s}: {len(subset):>8,} records")

            if channel_summaries:
                write_channel_summary(subset, summaries_dir / f"channels_us_{state}.csv")

    # ── Step 12: Summary ──────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"Done!")
    print(f"\n  Input CSVs processed : {len(frames)}")
    print(f"  Total unique records : {len(master):,}")

    print(f"\n  Type breakdown:")
    for t, c in master["Type"].value_counts().items():
        print(f"    {t:10s}: {c:>8,}")

    print(f"\n  Top 15 countries (by record count):")
    for country, count in country_counts.head(15).items():
        print(f"    {country:20s}: {count:>8,}")

    if not us_records.empty:
        print(f"\n  US states (by record count):")
        for state, count in us_records["state"].value_counts().items():
            print(f"    {state:20s}: {count:>8,}")

    print(f"\n  Output structure:")
    print(f"    {output_root}/")
    print(f"    ├── wigle_master_deduped.csv")
    print(f"    ├── wigle_no_gps.csv")
    print(f"    ├── countries/")
    print(f"    │   └── wigle_<country>.csv  ({len(has_geo['country'].unique())} files)")
    if not us_records.empty:
        print(f"    ├── us_states/")
        print(f"    │   └── wigle_us_<state>.csv  ({len(us_records['state'].unique())} files)")
    if channel_summaries:
        print(f"    └── channel_summaries/")
        print(f"        └── channels_<region>.csv  (per-region channel distribution)")


if __name__ == "__main__":
    main()
