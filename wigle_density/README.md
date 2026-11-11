# wigle_density

Counts recent WiFi networks per 2 km grid cell from the WiGLE API and writes `wigle_density.csv`. It feeds the [Wardrive Route Planner](https://github.com/FusedStamen/wardrive-route-planner), which uses it to value cells nobody has recorded yet ([how the planner uses it](https://github.com/FusedStamen/wardrive-route-planner/blob/main/docs/density.md)). It also works on its own as a density map.

Python 3.8 or newer, standard library only. No Docker. It never prints or stores your token anywhere except the config file you fill in.

## What it does

- Splits an area into boxes of N x N grid cells (cells are 0.02 degrees, `i = floor(lat/0.02)`, `j = floor(lon/0.02)`).
- Asks WiGLE for the total WiFi networks in each box, restricted to networks last updated since a cutoff date. One query per box, and it asks for one result per page, so almost no data moves.
- Spreads each box's total evenly over its cells (or counts cells exactly with `--box-cells 1`, or re-queries the densest boxes cell by cell with `--refine-top`).
- Saves every finished box in a cache after each query, so a daily limit never loses work. Re-running the same command resumes.

Output columns: `i,j,lat,lon,wifi_recent` (lat and lon are the cell centre).

## Setup

1. Get an API name and token from your WiGLE account page.
2. Run `python wigle_density.py` once. It creates `wigle_config.json` next to the script and stops.
3. Fill in `api_name` and `api_token`, or paste the "Encoded for use" value into `encoded`. Environment variables `WIGLE_API_NAME` + `WIGLE_API_TOKEN` (or `WIGLE_API_ENCODED`) also work.
4. Run the diagnostic once:

   ```
   python wigle_density.py --test
   ```

   It makes about 7 queries on a 3 x 3 box (default: central Boston, change with `--test-center LAT LON`) and checks that your account can use the API, that `totalResults` is returned, that the date filter shrinks the counts, that the two halves of a box add up to the whole, and which date format WiGLE accepts. It writes `wigle_test_report.txt`, which contains no credentials.

If you see "SSL certificate problem" (seen on Python 3.14 on Windows), run `pip install certifi`. The script uses it automatically when installed.

## Running it

```
python wigle_density.py --since 20241101 --center 27.95 -82.46 --radius-km 40 --box-cells 5
python wigle_density.py --since 20241101 --bbox 27.6 -83.0 28.4 -82.0
```

`--bbox` is `S W N E`. Boxes are queried nearest to the centre first. The result is `wigle_density.csv` next to the script; upload it in the planner page ("Recent WiGLE density" card).

| Option | Default | Effect |
|---|---|---|
| `--since YYYYMMDD` | first of this month, 2 years back | Cutoff for "recent". Pin it, see below |
| `--center LAT LON`, `--radius-km` | radius 40 | Area as a circle's bounding box |
| `--bbox S W N E` | | Area as a box |
| `--box-cells N` | 3 | Box size in cells. 3 is about 6.7 km, 5 about 11 km. Bigger means fewer queries and a coarser spread |
| `--refine-top K` | 0 | Re-query the K densest boxes cell by cell after the coarse pass |
| `--refine-min N` | 150 | Only refine boxes with at least this many networks |
| `--max-queries N` | 400 | Stop after N queries this run |
| `--delay SECONDS` | 1.0 | Pause between queries |
| `--cells FILE` | | CSV with `i,j` columns; only query boxes containing those cells |
| `--build-only` | | Rebuild the CSV from the cache, no API calls |
| `--test`, `--test-center` | | Diagnostic |

Query cost: a 40 km radius with `--box-cells 5` is about 80 queries; with `--box-cells 3`, about 220. `--refine-top` adds up to N x N queries per refined box.

## One growing file

Cells use the global grid index, so one file serves any area. Every finished box stays in `wigle_density_cache.json`, and each run rebuilds the CSV from the whole cache. Add areas as you need them and upload the newest CSV.

The cache is stored per cutoff. **Use the same `--since` on every run.** The default cutoff moves forward each month; a different cutoff starts a separate set and the CSV only contains the current cutoff.

## Choosing the cutoff

WiGLE's `lastupdt` is the last time a network was re-seen, not when it was first found. In busy areas almost everything is re-seen, so a 5-year cutoff barely filters (in one dense test box: about 445,000 networks with no filter, 443,000 for 5 years, 228,000 for 1 year). A 1 or 2 year cutoff separates current density from stale data. Rural areas are re-scanned rarely, so short cutoffs can undercount them.

## Limits and good behaviour

- WiGLE's API limits are per account and adaptive. On a limit (HTTP 429 or a "too many queries" message) the script stops, keeps its progress and tells you to re-run later.
- HTTP 401 means the name or token is wrong. HTTP 403 means WiGLE refused the account for API use.
- Follow WiGLE's API terms and limits. This tool only reads counts and stores only counts per cell, no network names or coordinates of individual networks.
- Files created next to the script: `wigle_config.json` (secret), `wigle_density_cache.json`, `wigle_density.csv`, `wigle_test_report.txt`. They are git-ignored here.

## How the counts are read

The tool uses the v2 network search endpoint (`/api/v2/network/search`) with `latrange1/2`, `longrange1/2`, `lastupdt`, `resultsPerPage=1` and reads `totalResults`. The `--test` diagnostic checks the behaviour it depends on (the filter shrinks the count, the halves add up to the whole) on your own account. It does not detect a hard cap on `totalResults` beyond the round-number warning it prints.

## Related

- [Wardrive Route Planner](https://github.com/FusedStamen/wardrive-route-planner): consumes the CSV. See its [docs/density.md](https://github.com/FusedStamen/wardrive-route-planner/blob/main/docs/density.md) for calibration and the fallback when no density file exists.
