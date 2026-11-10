# wigle_cell_heat

Turns your own WiGLE exports into a per-cell heat table, so you can see where you have already collected heavily and where you have not. Useful for planning drives that avoid ground you have covered, or for lining up against a 0.02 degree grid game map.

- Reads `.csv`, `.csv.gz`, and `.zip` files (zips may contain csvs) anywhere under the folder you give it
- Streams the files row by row, so 1 GB or more of exports is fine
- Makes no network requests; only reads files
- Grid: `i = floor(lat/0.02)`, `j = floor(lon/0.02)` (about 2 km cells)

## Usage

```bash
py wigle_cell_heat.py "E:\wardrive\Wigle Full Downloads"      # Windows
python3 wigle_cell_heat.py /path/to/exports                   # Linux/Mac
```

## Output (written inside the folder you pass in)

| File | Contents |
|------|----------|
| `wigle_cell_heat.csv` | One row per cell, heaviest first: `i, j, lat, lon, obs, nets, wifi_nets, ble_nets, files, first, last` |
| `wigle_cell_heat_summary.txt` | Totals, cells touched, how many cells pass 100/500/1000/5000 distinct networks, top 30 cells, skipped files |

`nets` is distinct networks (MAC) in the cell, with WiFi and BLE counted separately. `files` is how many of your log files touched the cell. The output has cell coordinates only, no MACs or SSIDs, so it is safe to share.

The same script is also kept in [FusedStamen/warroom](https://github.com/FusedStamen/warroom), where it is used alongside the route planning tools.
