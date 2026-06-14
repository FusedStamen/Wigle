#!/usr/bin/env python3
"""
wigle_channel_compare.py — Side-by-side channel distribution comparison for two WiGLE datasets.

Useful for comparing scan configurations, e.g.:
  Config A: 12 nodes on 1 device
  Config B: 6 nodes on each of 2 devices

Usage:
  python wigle_channel_compare.py --a path/to/configA/ --b path/to/configB/
  python wigle_channel_compare.py --a scan_a.csv --b scan_b.csv
  python wigle_channel_compare.py --a scan_a.csv --b scan_b.csv --label-a "12x1" --label-b "6x2" --out report.csv

Inputs can be a single WiGLE CSV file or a directory of CSVs (searched recursively).
Deduplication is per-dataset by MAC address (keeps strongest RSSI), matching wigle_sort behavior.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ── Channel classification (mirrored from wigle_sort_v3) ─────────────────────

WIFI_5_UNII1 = list(range(36, 52, 4))    # 36,40,44,48
WIFI_5_UNII2 = list(range(52, 100, 4))   # 52–96  (UNII-2A/2C, includes DFS)
WIFI_5_UNII3 = list(range(100, 150, 4))  # 100–148 (DFS)
WIFI_5_UNII4 = list(range(149, 178, 4))  # 149–177


def channel_band(ch):
    try:
        ch = int(float(ch))
    except (ValueError, TypeError):
        return "unknown"
    if 1 <= ch <= 14:
        return "2.4GHz"
    if 36 <= ch <= 177:
        return "5GHz"
    return "unknown"


def channel_unii(ch):
    """Return UNII band label for 5GHz channels, or None for 2.4GHz/unknown."""
    try:
        ch = int(float(ch))
    except (ValueError, TypeError):
        return None
    if ch in WIFI_5_UNII1:
        return "UNII-1 (36-48, no DFS)"
    if ch in WIFI_5_UNII2:
        return "UNII-2A/2C (52-96, DFS)"
    if ch in WIFI_5_UNII3:
        return "UNII-3 (100-148, DFS)"
    if ch in WIFI_5_UNII4:
        return "UNII-4 (149-177, no DFS)"
    return None


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_csvs(path: Path) -> pd.DataFrame:
    """Load one CSV file or all CSVs under a directory. Returns merged DataFrame."""
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.rglob("*.csv"))
        if not files:
            sys.exit(f"No CSV files found under: {path}")

    frames = []
    for f in files:
        try:
            df = pd.read_csv(
                f, skiprows=1, low_memory=False,
                encoding="utf-8", encoding_errors="replace"
            )
            if "MAC" not in df.columns or "Type" not in df.columns:
                print(f"  [skip] missing MAC/Type columns: {f.name}")
                continue
            frames.append(df)
        except Exception as e:
            print(f"  [skip] {f.name}: {e}")

    if not frames:
        sys.exit("No valid WiGLE CSVs could be loaded.")

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Loaded {len(combined):,} raw rows from {len(files)} file(s)")
    return combined


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to WiFi, deduplicate by MAC (keep strongest RSSI), classify channels."""
    df["Type"] = df["Type"].astype(str).str.upper().str.strip()
    wifi = df[df["Type"] == "WIFI"].copy()

    # Deduplicate by MAC, keep best RSSI
    if "RSSI" in wifi.columns:
        wifi["RSSI"] = pd.to_numeric(wifi["RSSI"], errors="coerce")
        wifi = wifi.sort_values("RSSI", ascending=False)
    wifi = wifi.drop_duplicates(subset=["MAC"], keep="first")

    wifi["channel_int"] = pd.to_numeric(wifi.get("Channel", pd.Series(dtype=float)), errors="coerce")
    wifi["band"] = wifi["channel_int"].apply(channel_band)
    wifi["unii"] = wifi["channel_int"].apply(channel_unii)

    print(f"  → {len(wifi):,} unique WiFi APs after dedup")
    return wifi


# ── Reporting ─────────────────────────────────────────────────────────────────

def band_summary(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["band"].value_counts().rename("count").reset_index()
    counts.columns = ["band", "count"]
    total = counts["count"].sum()
    counts["pct"] = (counts["count"] / total * 100).round(1)
    return counts.sort_values("band")


def channel_table(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["band"] != "unknown"].copy()
    tbl = (
        valid.groupby(["channel_int", "band", "unii"])
        .size()
        .reset_index(name="count")
        .sort_values(["band", "channel_int"])
    )
    total = tbl["count"].sum()
    tbl["pct"] = (tbl["count"] / total * 100).round(2)
    return tbl


def print_band_comparison(label_a, band_a, label_b, band_b):
    # Merge on band
    merged = pd.merge(
        band_a.rename(columns={"count": f"{label_a}_count", "pct": f"{label_a}_pct"}),
        band_b.rename(columns={"count": f"{label_b}_count", "pct": f"{label_b}_pct"}),
        on="band", how="outer"
    ).fillna(0)
    merged["pct_delta"] = (merged[f"{label_b}_pct"] - merged[f"{label_a}_pct"]).round(1)

    print(f"\n{'─'*70}")
    print(f"  BAND SUMMARY")
    print(f"{'─'*70}")
    hdr = f"  {'Band':<12}  {label_a:>12} {'%':>7}    {label_b:>12} {'%':>7}    {'Δ%':>7}"
    print(hdr)
    print(f"  {'-'*12}  {'-'*12} {'-'*7}    {'-'*12} {'-'*7}    {'-'*7}")
    for _, row in merged.iterrows():
        delta_str = f"{row['pct_delta']:+.1f}"
        print(
            f"  {row['band']:<12}  "
            f"{int(row[f'{label_a}_count']):>12,} {row[f'{label_a}_pct']:>6.1f}%    "
            f"{int(row[f'{label_b}_count']):>12,} {row[f'{label_b}_pct']:>6.1f}%    "
            f"{delta_str:>7}"
        )
    return merged


def print_channel_comparison(label_a, ch_a, label_b, ch_b, top_n=20):
    merged = pd.merge(
        ch_a[["channel_int", "band", "unii", "count", "pct"]].rename(
            columns={"count": f"{label_a}_count", "pct": f"{label_a}_pct"}),
        ch_b[["channel_int", "band", "count", "pct"]].rename(
            columns={"count": f"{label_b}_count", "pct": f"{label_b}_pct"}),
        on=["channel_int", "band"], how="outer"
    ).fillna(0).sort_values(["band", "channel_int"])

    merged["pct_delta"] = (merged[f"{label_b}_pct"] - merged[f"{label_a}_pct"]).round(2)

    print(f"\n{'─'*90}")
    print(f"  PER-CHANNEL BREAKDOWN  (sorted by band → channel)")
    print(f"{'─'*90}")
    hdr = (f"  {'Ch':>4}  {'Band':<8}  {'UNII Group':<28}  "
           f"{label_a:>10} {'%':>6}    {label_b:>10} {'%':>6}    {'Δ%':>7}")
    print(hdr)
    print(f"  {'-'*4}  {'-'*8}  {'-'*28}  {'-'*10} {'-'*6}    {'-'*10} {'-'*6}    {'-'*7}")

    for _, row in merged.iterrows():
        unii = str(row.get("unii", "") or "").split(" (")[0] if row["band"] == "5GHz" else ""
        delta_str = f"{row['pct_delta']:+.2f}"
        flag = ""
        if abs(row["pct_delta"]) >= 1.0:
            flag = " ◄" if row["pct_delta"] > 0 else " ▼"
        print(
            f"  {int(row['channel_int']):>4}  {row['band']:<8}  {unii:<28}  "
            f"{int(row[f'{label_a}_count']):>10,} {row[f'{label_a}_pct']:>5.2f}%    "
            f"{int(row[f'{label_b}_count']):>10,} {row[f'{label_b}_pct']:>5.2f}%    "
            f"{delta_str:>7}{flag}"
        )

    print(f"\n  ◄ = {label_b} higher by ≥1%   ▼ = {label_a} higher by ≥1%")
    return merged


def save_report(label_a, label_b, band_merged, ch_merged, out_path: Path):
    with open(out_path, "w") as f:
        f.write(f"# WiGLE Channel Comparison: {label_a} vs {label_b}\n\n")
        f.write("## Band Summary\n")
        band_merged.to_csv(f, index=False)
        f.write("\n## Per-Channel Breakdown\n")
        ch_merged.to_csv(f, index=False)
    print(f"\n  Report saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare channel distributions between two WiGLE scan datasets"
    )
    parser.add_argument("--a", required=True, metavar="PATH",
                        help="Config A: CSV file or directory of WiGLE CSVs")
    parser.add_argument("--b", required=True, metavar="PATH",
                        help="Config B: CSV file or directory of WiGLE CSVs")
    parser.add_argument("--label-a", default="Scan_A",
                        help="Label for dataset A (default: Config_A)")
    parser.add_argument("--label-b", default="Scan_B",
                        help="Label for dataset B (default: Config_B)")
    parser.add_argument("--out", metavar="FILE",
                        help="Optional: save CSV report to this file")
    args = parser.parse_args()

    la, lb = args.label_a, args.label_b

    print(f"\n[{la}] Loading from: {args.a}")
    raw_a = load_csvs(Path(args.a))
    wifi_a = prepare(raw_a)

    print(f"\n[{lb}] Loading from: {args.b}")
    raw_b = load_csvs(Path(args.b))
    wifi_b = prepare(raw_b)

    band_a = band_summary(wifi_a)
    band_b = band_summary(wifi_b)
    ch_a = channel_table(wifi_a)
    ch_b = channel_table(wifi_b)

    print(f"\n{'═'*70}")
    print(f"  WIGLE CHANNEL COMPARISON")
    print(f"  A: {la}   |   B: {lb}")
    print(f"{'═'*70}")

    band_merged = print_band_comparison(la, band_a, lb, band_b)
    ch_merged = print_channel_comparison(la, ch_a, lb, ch_b)

    if args.out:
        save_report(la, lb, band_merged, ch_merged, Path(args.out))


if __name__ == "__main__":
    main()
