#!/usr/bin/env python3
"""
wigle_sort.py — WiGLE CSV merger and region splitter
Usage: python wigle_sort.py --input "E:\TECH DATA\wardrive\Wigle Full Downloads" --output "E:\TECH DATA\wardrive\Wigle Sorted"

Merges all WiGLE CSVs across month folders, deduplicates by MAC+Type,
and splits into clean region files.
"""

import os
import argparse
import pandas as pd
from pathlib import Path

# ── Region bounding boxes ─────────────────────────────────────────────────────
REGIONS = {
    "india":    dict(lat_min=8.0,   lat_max=37.0,  lon_min=68.0,  lon_max=98.0),
    "europe":   dict(lat_min=34.0,  lat_max=72.0,  lon_min=-25.0, lon_max=45.0),
    "us":       dict(lat_min=24.0,  lat_max=50.0,  lon_min=-125.0,lon_max=-65.0),
    "canada":   dict(lat_min=41.0,  lat_max=84.0,  lon_min=-141.0,lon_max=-52.0),
}

def in_region(lat, lon, r):
    return r["lat_min"] <= lat <= r["lat_max"] and r["lon_min"] <= lon <= r["lon_max"]

def classify(lat, lon):
    for name, bbox in REGIONS.items():
        if in_region(lat, lon, bbox):
            return name
    return "other"

def read_wigle_csv(path):
    """Read a WiGLE CSV, skipping the metadata header line."""
    try:
        df = pd.read_csv(path, skiprows=1, low_memory=False)
        # Must have at minimum MAC and Type columns
        if "MAC" not in df.columns or "Type" not in df.columns:
            print(f"  SKIP (bad headers): {path.name}")
            return None
        return df
    except Exception as e:
        print(f"  SKIP (error): {path.name} — {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="WiGLE CSV merger and region splitter")
    parser.add_argument("--input",  required=True, help="Root folder containing month subfolders")
    parser.add_argument("--output", required=True, help="Output folder for sorted CSVs")
    parser.add_argument("--types",  default="WIFI,BLE,BT,GSM,LTE,WCDMA",
                        help="Comma-separated types to include (default: all)")
    args = parser.parse_args()

    input_root  = Path(args.input)
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    keep_types = set(t.strip().upper() for t in args.types.split(","))

    # ── Step 1: Find all CSVs ─────────────────────────────────────────────────
    csv_files = sorted(input_root.rglob("*.csv"))
    print(f"Found {len(csv_files)} CSV files across all month folders")

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

    # ── Step 3: Filter to requested types ────────────────────────────────────
    master["Type"] = master["Type"].astype(str).str.upper().str.strip()
    master = master[master["Type"].isin(keep_types)]
    print(f"  Rows after type filter:  {len(master):,}")

    # ── Step 4: Deduplicate by MAC + Type ─────────────────────────────────────
    # Keep the row with the best (strongest) RSSI signal for each MAC+Type
    master["RSSI"] = pd.to_numeric(master["RSSI"], errors="coerce")
    master = master.sort_values("RSSI", ascending=False)
    master = master.drop_duplicates(subset=["MAC", "Type"], keep="first")
    print(f"  Rows after dedup:        {len(master):,}")

    # ── Step 5: Classify regions ──────────────────────────────────────────────
    master["CurrentLatitude"]  = pd.to_numeric(master["CurrentLatitude"],  errors="coerce")
    master["CurrentLongitude"] = pd.to_numeric(master["CurrentLongitude"], errors="coerce")

    valid_geo = master.dropna(subset=["CurrentLatitude", "CurrentLongitude"])
    no_geo    = master[master["CurrentLatitude"].isna() | master["CurrentLongitude"].isna()]

    print(f"\nClassifying {len(valid_geo):,} geolocated records...")
    valid_geo = valid_geo.copy()
    valid_geo["region"] = valid_geo.apply(
        lambda r: classify(r["CurrentLatitude"], r["CurrentLongitude"]), axis=1
    )

    # ── Step 6: Write output files ────────────────────────────────────────────
    # WiGLE header line for compatibility
    wigle_header = "WigleWifi-1.4,appRelease=2.x,model=SERVER,release=2.50,device=WiGLE SERVER,display=NONE,brand=WiGLE.net\n"

    def write_region(df, name):
        if df.empty:
            return
        out_path = output_root / f"wigle_{name}.csv"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(wigle_header)
        # Drop the internal region column before saving
        out_df = df.drop(columns=["region"], errors="ignore")
        out_df.to_csv(out_path, mode="a", index=False)
        print(f"  Wrote {len(df):,} records → {out_path.name}")

    print(f"\nWriting region files to {output_root}...")
    for region_name in list(REGIONS.keys()) + ["other"]:
        subset = valid_geo[valid_geo["region"] == region_name].drop(columns=["region"])
        write_region(subset.assign(region=region_name), region_name)
        # re-assign since we dropped it above
        subset_out = valid_geo[valid_geo["region"] == region_name].drop(columns=["region"])
        out_path = output_root / f"wigle_{region_name}.csv"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(wigle_header)
        subset_out.to_csv(out_path, mode="a", index=False)
        print(f"  {region_name:10s}: {len(subset_out):>8,} records → wigle_{region_name}.csv")

    # Master deduped file (all regions)
    master_out = output_root / "wigle_master_deduped.csv"
    with open(master_out, "w", encoding="utf-8") as f:
        f.write(wigle_header)
    master.drop(columns=["region"], errors="ignore").to_csv(master_out, mode="a", index=False)
    print(f"\n  Master deduped: {len(master):,} records → wigle_master_deduped.csv")

    if not no_geo.empty:
        no_geo_out = output_root / "wigle_no_gps.csv"
        with open(no_geo_out, "w", encoding="utf-8") as f:
            f.write(wigle_header)
        no_geo.to_csv(no_geo_out, mode="a", index=False)
        print(f"  No GPS data:    {len(no_geo):,} records → wigle_no_gps.csv")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"Done! Summary:")
    print(f"  Input CSVs processed:  {len(frames)}")
    print(f"  Total unique records:  {len(master):,}")
    type_counts = master["Type"].value_counts()
    for t, c in type_counts.items():
        print(f"    {t:8s}: {c:>8,}")
    print(f"\n  Region breakdown (geolocated):")
    region_counts = valid_geo["region"].value_counts()
    for r, c in region_counts.items():
        print(f"    {r:10s}: {c:>8,}")

if __name__ == "__main__":
    main()
