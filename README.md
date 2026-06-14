# Wigle_Sort

WiGLE CSV merger, deduplicator, and region splitter for wardriving data.

---

## Versions

| Version | File | Description |
|---------|------|-------------|
| v1 | `wigle_sort.py` | 4-region splitter (US, India, Europe, Canada) |
| v2 | `wigle_sort_v2.py` | 46 countries + all 50 US states/DC + channel analysis |

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
python wigle_sort_v2.py \
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

**Output — v2**

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

## How it works

### Input
Both versions recursively scan `--input` for all `*.csv` files. WiGLE CSV exports have a metadata header line on row 1 - both scripts skip it automatically. Files with missing or malformed headers are skipped with a warning.

### Deduplication
Records are deduplicated by `MAC + Type`. Where the same MAC appears across multiple sessions, the row with the strongest RSSI is kept.

### Classification
Both versions use bounding box classification - latitude/longitude ranges per region. No reverse geocoding, no internet dependency.

- **v1** - 4 coarse regions: US, India, Europe (entire continent), Canada
- **v2** - 46 individual countries + all 50 US states + Washington DC. US records are written to both `countries/wigle_usa.csv` and the appropriate `us_states/` file.

Records with `0,0` coordinates, impossible values, or coordinates that fall outside all bounding boxes (e.g. open ocean) go to `wigle_other.csv` / `other` bucket.

### Channel analysis (v2 only)
For every output region and state, a `channel_summaries/channels_<region>.csv` is generated containing:
- Band totals (2.4 GHz vs 5 GHz)
- Per-channel record counts
- 5 GHz channels grouped by UNII band

| UNII Band | Channels |
|-----------|----------|
| UNII-1 | 36–48 |
| UNII-2A/2C | 52–96 |
| UNII-3 (DFS) | 100–148 |
| UNII-4 | 149–177 |

---

## v1 → v2 Changes

### Bug fixes
- **Double-write bug fixed** - v1 wrote every region file twice due to a logic error in the write loop, with the second write silently overwriting the first.

### New features
- 46 countries instead of 4 coarse regions
- All 50 US states + DC with individual bounding boxes
- Channel analysis output per region and state
- Structured subdirectory output instead of flat folder
- `--no-channel-summaries` flag
- Improved terminal summary with top 15 countries and full state breakdown

## v2 → v3 Changes

### Bug fixes
- **Small State Fix** - v3 introduces a bbox_area() helper that computes the area of each bounding box, then pre-sorts both COUNTRIES and US_STATES by area (smallest first) at module load time into _COUNTRIES_SORTED and _US_STATES_SORTED. The classify_location() function then iterates over those sorted lists instead of the original unsorted dicts.

---

## Notes

- Offshore/ocean coordinates (e.g. Atlantic coast GPS drift, ferry captures) correctly land in `other` — this is expected behavior
- Coastal state bounding boxes (FL, NJ, NY, NC, SC, ME, MI) are extended slightly past land borders to capture barrier island and waterfront GPS
- `wigle_no_gps.csv` contains records with null or missing coordinates - these are excluded from all region files but preserved in the master deduped file
