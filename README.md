# Wigle

Tools and write-ups for working with [WiGLE](https://wigle.net) wardriving data: sorting and merging your own exports, planning where to drive next, and checking uploads for spam contamination.

---

## What is here

| Folder / file | What it does | Status |
|---------------|--------------|--------|
| [`wigle_sort/`](wigle_sort/) | Merge all your WiGLE CSV exports, dedupe by MAC + Type, split by country and US state, write channel summaries and a paste-ready stats snippet. **v4 streams through SQLite and handles multi-GB exports.** | Working |
| [`wigle_sort/wigle_channel_compare.py`](wigle_sort/) | Side-by-side channel distribution comparison between two scan datasets (A/B test scan setups). | Working |
| [`beacon_spam_detector/`](beacon_spam_detector/) | Design notes for a self-contained spam/SSID-spoof detector that needs no personal baseline. | In progress, script not published yet |
| [`beacon_spam_contamination/`](beacon_spam_contamination/) | Write-up of the firmware teardown hypothesis for self-logged spam beacons, and how it was ruled out. | Closed |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history for `wigle_sort`. | |

### Related tools in other repos

These work with WiGLE data too and live in [FusedStamen/warroom](https://github.com/FusedStamen/warroom):

| Tool | What it does |
|------|--------------|
| `wigle_cell_heat.py` | Turns your own WiGLE exports (`.csv`, `.csv.gz`, `.zip`) into a per-cell heat table on the 0.02 degree grid, so you can see where you have already collected heavily and where you have not. Streams the files and makes no network calls. |
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

Then see where you have already driven heavily (from the warroom repo):

```bash
py wigle_cell_heat.py "E:\wardrive\Wigle Full Downloads"
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
