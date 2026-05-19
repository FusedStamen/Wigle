# wigle_sort.py — v1 → v2 Changelog

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
