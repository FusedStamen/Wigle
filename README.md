# Wigle

Tools and write-ups for working with [WiGLE](https://wigle.net) wardriving data: sorting and merging your own exports, planning where to drive next, and checking uploads for spam contamination.

---

## What is here

| Folder / file | What it does | Status |
|---------------|--------------|--------|
| [`wigle_sort/`](wigle_sort/) | Merge all your WiGLE CSV exports, dedupe by MAC + Type, split by country and US state, write channel summaries and a paste-ready stats snippet. **v4 streams through SQLite and handles multi-GB exports.** | Working |
| [`wigle_cell_heat/`](wigle_cell_heat/) | Turns your own WiGLE exports (`.csv`, `.csv.gz`, `.zip`) into a per-cell heat table on a 0.02 degree grid, to see where you have already collected heavily. Streams files, no network calls. Writes `wigle_cell_heat.csv`, which the [wardrive route planner](https://github.com/FusedStamen/wardrive-route-planner) uses. | Working |
| [`wigle_density/`](wigle_density/) | Uses the WiGLE API to count recently seen WiFi networks per 0.02 degree cell for an area, so unvisited cells can be valued. Quota-aware, cached and resumable. Output feeds the [wardrive route planner](https://github.com/FusedStamen/wardrive-route-planner). | Working |
| [`wigle_sort/wigle_channel_compare.py`](wigle_sort/) | Side-by-side channel distribution comparison between two scan datasets (A/B test scan setups). | Working |
| [`beacon_spam_contamination/`](beacon_spam_contamination/) | Write-up of the firmware teardown hypothesis for self-logged spam beacons, and how it was ruled out. | Closed |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history for `wigle_sort`. | |

### Related tools in other repos

The planner that consumes the heat and density files, and one gap-street tool, live in other repos.

| Tool | What it does |
|------|--------------|
| [wardrive-route-planner](https://github.com/FusedStamen/wardrive-route-planner) | Phone-first route planner for the WDGoWars game. Uses `wigle_cell_heat.csv` and `wigle_density.csv` from this repo. |

The next one uses the WiGLE API and lives in [FusedStamen/warroom](https://github.com/FusedStamen/warroom):

| Tool | What it does |
|------|--------------|
| `find_gap_streets.py` | Finds residential streets with no WiGLE coverage and builds a GPX route. Quota-aware and resumable. Uses the WiGLE API. |

---

## Quick start

Sort and split a full history of exports (Windows paths shown, use `python3` on Linux/Mac):

```bash
py wigle_sort/wigle_sort_v4.py --input "E:\wardrive\Wigle Full Downloads" --output "E:\wardrive\Wigle Sorted"
```

Output:

```
Wigle Sorted/
├── wigle_master_deduped.csv
├── wigle_no_gps.csv
├── readme_stats.md
├── countries/            wigle_<country>.csv
├── us_states/            wigle_us_<state>.csv
└── channel_summaries/    channels_<region>.csv
```

Then see where you have already driven heavily (heat table of your own coverage):

```bash
py wigle_cell_heat/wigle_cell_heat.py "E:\wardrive\Wigle Full Downloads"
```

Value unvisited cells from recent WiGLE density (uses the API, needs a key, see [`wigle_density/README.md`](wigle_density/README.md)):

```bash
py wigle_density/wigle_density.py --center LAT LON --radius-km KM
```

Full options for `wigle_sort` are in [`wigle_sort/README.md`](wigle_sort/README.md).

---

## Good to know

- **Server exports have no channel data.** WiGLE's website exports log `-1` for Channel on every row. For channel analysis use local device logs.
- **Classification is by bounding box**, no reverse geocoding and no internet needed. Coastal state boxes are slightly extended to catch barrier-island and waterfront GPS. Offshore points land in `other`.
- **Your exports contain MACs and SSIDs.** Keep them out of git. Nothing in this repo needs them committed.

---

## License

MIT, see [LICENSE](LICENSE).
