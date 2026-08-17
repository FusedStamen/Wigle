# Wigle_Sort

WiGLE CSV merger, deduplicator, region splitter, and channel analyzer for wardriving data.

---

## Versions

| Version | File | Description |
|---------|------|-------------|
| v1 | `wigle_sort.py` | 4-region splitter (US, India, Europe, Canada) |
| v2 | `wigle_sort_v2.py` | 46 countries + all 50 US states/DC + channel analysis |
| v3 | `wigle_sort_v3.py` | v2 + small state bounding box fix (RI, DC, etc.) |
| — | `wigle_channel_compare.py` | Side-by-side channel distribution comparison between two scan datasets |

---

## Requirements

```bash
pip install pandas
```

Python 3.8+

---

## Usage

### v1

```bash
python wigle_sort.py \
  --input  "E:\TECH DATA\wardrive\Wigle Full Downloads" \
  --output "E:\TECH DATA\wardrive\Wigle Sorted"
```

**Arguments**

| Flag | Required | Description |
|------|----------|-------------|
| `--input` | ✅ | Root folder containing WiGLE CSV files (searched recursively) |
| `--output` | ✅ | Output folder for sorted CSVs |
| `--types` | ❌ | Comma-separated types to include. Default: `WIFI,BLE,BT,GSM,LTE,WCDMA` |

**Output — v1**

```
output/
├── wigle_us.csv
├── wigle_india.csv
├── wigle_europe.csv
├── wigle_canada.csv
├── wigle_other.csv
├── wigle_master_deduped.csv
└── wigle_no_gps.csv
```

---

### v2, v3

```bash
python wigle_sort_v3.py \
  --input  "E:\TECH DATA\wardrive\Wigle Full Downloads" \
  --output "E:\TECH DATA\wardrive\Wigle Sorted"
```

**Arguments**

| Flag | Required | Description |
|------|----------|-------------|
| `--input` | ✅ | Root folder containing WiGLE CSV files (searched recursively) |
| `--output` | ✅ | Output folder for sorted CSVs |
| `--types` | ❌ | Comma-separated types to include. Default: `WIFI,BLE,BT,GSM,LTE,WCDMA` |
| `--no-channel-summaries` | ❌ | Skip channel analysis CSVs for faster runs |

**Output — v2/v3**

```
output/
├── wigle_master_deduped.csv
├── wigle_no_gps.csv
├── countries/
│   ├── wigle_usa.csv
│   ├── wigle_india.csv
│   ├── wigle_netherlands.csv
│   └── wigle_<country>.csv   (46 countries total)
├── us_states/
│   ├── wigle_us_massachusetts.csv
│   ├── wigle_us_texas.csv
│   └── wigle_us_<state>.csv  (50 states + DC)
└── channel_summaries/
    ├── channels_usa.csv
    ├── channels_us_massachusetts.csv
    └── channels_<region>.csv
```

---

### wigle_channel_compare.py

Compares channel distributions between two WiGLE scan datasets side by side. Useful for A/B testing scan configurations — for example, comparing 12 nodes on 1 device vs 6 nodes on 2 devices to see how node distribution affects 2.4 GHz vs 5 GHz coverage.

> **Note:** WiGLE server-side CSV exports strip channel data, logging `-1` for all records. Run this script against local device logs (e.g. Biscuit Ultra exports) that retain real channel values.

```bash
# Single CSV files
python wigle_channel_compare.py --a scan_a.csv --b scan_b.csv

# Whole directories (reads all CSVs recursively, same as wigle_sort)
python wigle_channel_compare.py --a ./scan_a/ --b ./scan_b/ --out compare.csv
```

**Arguments**

| Flag | Required | Description |
|------|----------|-------------|
| `--a` | ✅ | Scan A: CSV file or directory of WiGLE-format CSVs |
| `--b` | ✅ | Scan B: CSV file or directory of WiGLE-format CSVs |
| `--label-a` | ❌ | Label for dataset A (default: `Scan_A`) |
| `--label-b` | ❌ | Label for dataset B (default: `Scan_B`) |
| `--out` | ❌ | Save CSV report to this file |

**Output**

Prints to terminal:

- Band summary (2.4 GHz vs 5 GHz count, percentage, and delta between scans)
- Per-channel breakdown with UNII group labels for 5 GHz channels
- Channels where the two scans diverge by ≥1% are flagged with `◄` or `▼`

Optionally saves a CSV report with both tables via `--out`.

**Deduplication**

Records are deduplicated by MAC within each dataset (keeping strongest RSSI) before any channel counts are calculated, matching wigle_sort behavior. This prevents long drives inflating counts for channels seen repeatedly.

---

## How it works

### Input
All scripts recursively scan their input path for `*.csv` files. WiGLE CSV exports have a metadata header on row 1 — all scripts skip it automatically. Files with missing or malformed headers are skipped with a warning.

### Deduplication
Records are deduplicated by `MAC + Type`. Where the same MAC appears across multiple sessions, the row with the strongest RSSI is kept.

### Classification
Both versions use bounding box classification — latitude/longitude ranges per region. No reverse geocoding, no internet dependency.

- **v1** — 4 coarse regions: US, India, Europe (entire continent), Canada
- **v2/v3** — 46 individual countries + all 50 US states + Washington DC. US records are written to both `countries/wigle_usa.csv` and the appropriate `us_states/` file.

Records with `0,0` coordinates, impossible values, or coordinates outside all bounding boxes (e.g. open ocean) go to `wigle_other.csv`.

### Channel analysis (v2, v3, and wigle_channel_compare)
For every output region and state, v2/v3 generate a `channel_summaries/channels_<region>.csv` containing band totals and per-channel counts. `wigle_channel_compare.py` performs the same analysis across two datasets and reports the delta.

| UNII Band | Channels |
|-----------|----------|
| UNII-1 | 36–48 |
| UNII-2A/2C | 52–96 |
| UNII-3 (DFS) | 100–148 |
| UNII-4 | 149–177 |

---

## Changelog

### v1 → v2

**Bug fixes**
- Double-write bug fixed — v1 wrote every region file twice due to a logic error in the write loop, with the second write silently overwriting the first.

**New features**
- 46 countries instead of 4 coarse regions
- All 50 US states + DC with individual bounding boxes
- Channel analysis output per region and state
- Structured subdirectory output instead of flat folder
- `--no-channel-summaries` flag
- Improved terminal summary with top 15 countries and full state breakdown

### v2 → v3

**Bug fixes**
- Small state fix — v3 introduces a `bbox_area()` helper that computes the area of each bounding box, then pre-sorts both `COUNTRIES` and `US_STATES` by area smallest-first at module load time. Classification then iterates the sorted lists so small states like Rhode Island match before larger overlapping neighbors like Massachusetts and Connecticut.

### wigle_channel_compare.py (new)

Standalone comparison tool for A/B testing scan configurations. Accepts local device logs directly since WiGLE server exports strip channel data. See usage above.

---

## Notes

- Offshore/ocean coordinates (e.g. Atlantic coast GPS drift, ferry captures) correctly land in `other` — this is expected behavior
- Coastal state bounding boxes (FL, NJ, NY, NC, SC, ME, MI) are extended slightly past land borders to capture barrier island and waterfront GPS
- `wigle_no_gps.csv` contains records with null or missing coordinates — excluded from all region files but preserved in the master deduped file
- WiGLE server-side CSV exports log `-1` for Channel on all records — use local device exports for any channel analysis
