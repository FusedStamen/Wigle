# Changelog

Newest first. Covers `wigle_sort` and the tools next to it.

---

## wigle_sort v3 -> v4 (streaming, low-memory)

v4 is a rewrite of how the data is handled, not of what comes out. Same output folder layout as v3.

**Why:** v3 reads every CSV into one pandas DataFrame, then sorts and dedupes it in memory. That works for a few hundred MB of exports and runs out of memory on a full multi-GB history.

**How v4 works**
- Pass 1 streams every input file row by row into a temporary SQLite file, keeping one row per MAC + Type (strongest RSSI wins).
- Pass 2 reads that table back one row at a time, classifies each row, and appends it to the output files. Only counters stay in memory.
- Measured on 2.5 million synthetic rows (about 200 MB of CSV): about 40 MB peak memory, about 80 seconds. Memory stays flat as input grows. Disk use during the run is roughly the size of the deduped data; the temp file is removed at the end.

**New**
- Reads `.csv`, `.csv.gz` and `.zip` files (zips may contain `.csv` or `.csv.gz`). v3 only read `.csv`.
- `--tmp-dir` flag to put the temporary SQLite file on a drive with free space.
- Skips anything inside the output folder, so a re-run never ingests its own output.
- No pandas dependency (standard library only).
- Values are written exactly as they were in the source files. v3 passed everything through pandas, which rewrote integer columns such as Channel as floats (`6.0`).

**Changed**
- `readme_stats.md`: "Countries covered" no longer counts the `other` bucket as a country.
- Channel summaries: channel numbers are integers (`6`, not `6.0`), and out-of-range values such as `-1` (WiGLE server exports) are grouped as `unknown` instead of `5GHz_ch-1`.
- Rows inside output files are ordered by MAC. v3 left them ordered by RSSI as a side effect of its sort.

**Unchanged**
- Dedupe rule (MAC + Type, strongest RSSI), bounding boxes, smallest-box-first matching, all CLI flags from v3.
- Checked against v3 on test data with no RSSI ties: same files, same rows, same channel counts.

**Known limit**
- Where two rows for the same MAC + Type have identical RSSI, v3 and v4 may keep different ones. It is arbitrary in both. It only affects which location is used for that network.

---

## wigle_sort v2 -> v3

**Bug fix**
- Small-state classification. v3 adds a `bbox_area()` helper and sorts `COUNTRIES` and `US_STATES` by bounding box area, smallest first, so Rhode Island and DC match before the larger overlapping boxes of Massachusetts, Connecticut and Maryland/Virginia.

**New**
- `readme_stats.md`: a paste-ready markdown stats snippet (totals, type breakdown, top 15 countries, US states) written on every run.
- `--no-readme-stats` flag to skip it.

---

## wigle_channel_compare.py (new)

Standalone A/B comparison of channel distributions between two WiGLE-format datasets. Takes local device logs, since WiGLE server exports strip channel data. See `wigle_sort/README.md`.

---

## wigle_sort v1 -> v2


## Bug Fixes

### Double-write bug (v1 lines 121–130)
The region write loop in v1 called `write_region()` and then immediately re-opened and re-wrote the same file manually. Every region file was written twice, with the second write silently overwriting the first.

**v1 (broken):**
```python
for region_name in list(REGIONS.keys()) + ["other"]:
    subset = valid_geo[valid_geo["region"] == region_name].drop(columns=["region"])
    write_region(subset.assign(region=region_name), region_name)   # ← write 1
    subset_out = valid_geo[valid_geo["region"] == region_name]...
    with open(out_path, "w") as f: f.write(wigle_header)
    subset_out.to_csv(out_path, mode="a", ...)                      # ← write 2 (overwrites write 1)
```

**v2 (fixed):** Single `write_csv()` helper, called once per file.

---

## Geographic Coverage

### v1 — 4 coarse regions
| Region  | Coverage |
|---------|----------|
| india   | Single country bounding box |
| europe  | Entire continent as one blob |
| us      | Entire USA as one blob |
| canada  | Entire Canada as one blob |
| other   | Everything else (most of the world) |

### v2 — 46 countries + 51 US states/DC
**Countries added:** UK, Ireland, France, Germany, Netherlands, Belgium, Switzerland, Austria, Spain, Portugal, Italy, Sweden, Norway, Denmark, Finland, Poland, Czechia, Hungary, Romania, Greece, China, Japan, South Korea, Taiwan, Singapore, Thailand, Vietnam, Indonesia, Malaysia, Philippines, Israel, UAE, Saudi Arabia, Australia, New Zealand, Brazil, Argentina, Colombia, Chile, South Africa, Nigeria, Kenya, Egypt, Mexico — plus retained India, Canada, USA.

**US states:** All 50 states + Washington DC, each with individual bounding boxes. Records in `countries/wigle_usa.csv` are also split into `us_states/wigle_us_<state>.csv`.

**"other" bucket** is now much smaller — only genuinely unclassifiable coordinates (bad GPS, open ocean) end up there.

---

## New Features

### Channel analysis
Every region and state gets a `channel_summaries/channels_<region>.csv` containing:
- Band totals (2.4 GHz vs 5 GHz record counts)
- Per-channel record counts
- 5 GHz channels grouped by UNII band:
  - UNII-1: channels 36–48
  - UNII-2A/2C: channels 52–96
  - UNII-3 (DFS): channels 100–148
  - UNII-4: channels 149–177

Use `--no-channel-summaries` flag to skip if you only want the split CSVs.

### Structured output directory layout
**v1:** All files dumped into one flat output folder.

**v2:** Organized into subdirectories:
```
output/
├── wigle_master_deduped.csv
├── wigle_no_gps.csv
├── countries/
│   └── wigle_<country>.csv
├── us_states/
│   └── wigle_us_<state>.csv
└── channel_summaries/
    └── channels_<region>.csv
```

### New CLI flag
`--no-channel-summaries` — skips writing channel summary CSVs for faster runs when you only need the split files.

### Improved terminal summary
v2 prints:
- Top 15 countries by record count
- All US states by record count
- Full output directory tree with file counts

---

## Removed

- The 4 hardcoded `REGIONS` dict and `classify()` function replaced by `COUNTRIES` + `US_STATES` dicts and separate `classify_country()` / `classify_us_state()` functions.
- `write_region()` inner function replaced by module-level `write_csv()` helper.
- `os` import removed (unused in v1, not needed in v2).
