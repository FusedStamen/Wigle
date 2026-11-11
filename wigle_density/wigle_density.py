#!/usr/bin/env python3
"""
wigle_density.py - recent WiGLE WiFi network density per 2 km grid cell.
Part of https://github.com/FusedStamen/Wigle - feeds the Wardrive Route Planner
(https://github.com/FusedStamen/wardrive-route-planner), see its docs/density.md.

Writes wigle_density.csv with columns: i,j,lat,lon,wifi_recent
  i = floor(lat/0.02), j = floor(lon/0.02), lat/lon = cell center.
  wifi_recent = WiGLE WiFi networks last updated since the cutoff date (default:
  2 years back), spread evenly over the cells of each query box.

Python 3.8+, standard library only. Run it from any folder; all files (config,
cache, output, test report) live next to this script.

STEP 1 - credentials
  Run the script once. It creates wigle_config.json next to itself. Open it in
  Notepad and fill in "api_name" and "api_token" from
  https://wigle.net/account (the "API Token" section). Alternatively paste the
  "Encoded for use" value into "encoded". Environment variables
  WIGLE_API_NAME + WIGLE_API_TOKEN (or WIGLE_API_ENCODED) work too.
  The script never prints or stores the token anywhere except that file.

STEP 2 - one diagnostic (do this first)
  python wigle_density.py --test
  Makes about 7 queries, checks that the API works for your account, that
  totalResults is returned, that the lastupdt filter really shrinks the count,
  and that splitting a box gives the same total. Writes wigle_test_report.txt.
  Share that report if you need help.

STEP 3 - real run
  python wigle_density.py --center 28.0 -82.5 --radius-km 60
  or
  python wigle_density.py --bbox 27.6 -83.0 28.4 -82.0      (S W N E)

  Boxes are queried nearest-to-center first. Finished boxes are saved in
  wigle_density_cache.json after every query, so if the daily limit hits (the
  script stops cleanly) just run the same command again the next day.
  Re-running with a different area adds to the same cache and the CSV always
  contains everything cached.

Useful options
  --box-cells N       query boxes of N x N cells (default 3, about 6.7 km).
                      1 = exact per-cell counts, but 9x the queries.
  --refine-top K      after the coarse pass, re-query the K densest boxes cell
                      by cell so dense spots are not smeared over empty ones.
  --since YYYYMMDD    cutoff for "recent" (default: same month, 2 years ago)
  --max-queries N     stop after N queries this run (default 400)
  --delay SECONDS     pause between queries (default 1.0)
  --cells FILE        csv with i,j columns; only query boxes that contain
                      these cells (skips water and empty land you do not need)
  --build-only        just rebuild the csv from the cache, no API calls
"""
import argparse
import base64
import csv
import datetime
import json
import math
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CELL = 0.02
API_URL = os.environ.get("WIGLE_API_URL", "https://api.wigle.net/api/v2/network/search")
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "wigle_config.json")
CACHE_PATH = os.path.join(HERE, "wigle_density_cache.json")
OUT_PATH = os.path.join(HERE, "wigle_density.csv")
REPORT_PATH = os.path.join(HERE, "wigle_test_report.txt")
EPS = 1e-6

# lastupdt format: documented as yyyyMMdd[hhmm[ss]]. Start with 8 digits and
# fall back to 14 digits if the API calls the format invalid.
_DATE_FORMATS = ["short", "long"]
_date_fmt = {"mode": "short"}


class LimitReached(Exception):
    pass


class AuthError(Exception):
    pass


class ApiError(Exception):
    pass


# ----------------------------------------------------------------- helpers
def cell_index(v):
    return int(math.floor(v / CELL + 1e-9))


def ssl_context():
    try:
        import certifi  # optional, fixes missing CA bundle on some Windows Pythons
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def load_auth():
    enc = os.environ.get("WIGLE_API_ENCODED", "").strip()
    name = os.environ.get("WIGLE_API_NAME", "").strip()
    tok = os.environ.get("WIGLE_API_TOKEN", "").strip()
    if not (enc or (name and tok)) and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            sys.exit("Could not read %s: %s" % (CONFIG_PATH, e))
        enc = str(cfg.get("encoded", "")).strip()
        name = str(cfg.get("api_name", "")).strip()
        tok = str(cfg.get("api_token", "")).strip()
    if not (enc or (name and tok)):
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"api_name": "", "api_token": "", "encoded": ""}, f, indent=2)
        sys.exit(
            "No WiGLE credentials found.\n"
            "Open this file in Notepad and fill in api_name and api_token\n"
            "(from https://wigle.net/account, API Token section):\n  %s\n"
            "Then run the command again." % CONFIG_PATH
        )
    if enc:
        return enc
    return base64.b64encode(("%s:%s" % (name, tok)).encode("utf-8")).decode("ascii")


def default_since():
    t = datetime.date.today()
    return "%04d%02d01" % (t.year - 2, t.month)


def since_param(since):
    return since if _date_fmt["mode"] == "short" else since + "000000"


def valid_since(s):
    if len(s) != 8 or not s.isdigit():
        sys.exit("--since must look like 20210601")
    try:
        datetime.datetime.strptime(s, "%Y%m%d")
    except ValueError:
        sys.exit("--since is not a real date: %s" % s)
    return s


# --------------------------------------------------------------------- API
def api_get(auth, ctx, params):
    url = API_URL + "?" + urllib.parse.urlencode(params)
    headers = {
        "Authorization": "Basic " + auth,
        "Accept": "application/json",
        "User-Agent": "wardrive-density/1.0",
    }
    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AuthError("HTTP 401 - WiGLE rejected the API name/token. Check wigle_config.json.")
            if e.code == 403:
                raise AuthError("HTTP 403 - WiGLE refused this account for API use (restricted or blocked?).")
            if e.code == 429:
                raise LimitReached("HTTP 429 - WiGLE query limit reached.")
            if e.code >= 500:
                last_err = "HTTP %d" % e.code
                time.sleep(3 * (attempt + 1))
                continue
            raise ApiError("HTTP %d from WiGLE" % e.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError):
                raise ApiError(
                    "SSL certificate problem (%s).\nFix: run  pip install certifi  and re-run. "
                    "The script uses certifi automatically when it is installed." % reason
                )
            last_err = str(reason)
            time.sleep(3 * (attempt + 1))
            continue
        try:
            data = json.loads(body)
        except ValueError:
            raise ApiError("WiGLE returned something that is not JSON: %r" % body[:120])
        if data.get("success") is False:
            msg = str(data.get("message", ""))
            low = msg.lower()
            if "too many" in low or "limit" in low or "exceed" in low:
                raise LimitReached("WiGLE said: " + msg)
            if "auth" in low or "login" in low or "unauthor" in low or "forbidden" in low:
                raise AuthError("WiGLE said: " + msg)
            raise ApiError("WiGLE said: " + msg)
        return data
    raise ApiError("Network problem after 3 tries: %s" % last_err)


def query(auth, ctx, lat1, lat2, lon1, lon2, since, per_page=1):
    """One box search. since=None means no lastupdt filter."""
    for _ in range(2):
        params = {
            "latrange1": "%.6f" % lat1,
            "latrange2": "%.6f" % lat2,
            "longrange1": "%.6f" % lon1,
            "longrange2": "%.6f" % lon2,
            "resultsPerPage": per_page,
            "onlymine": "false",
        }
        if since:
            params["lastupdt"] = since_param(since)
        try:
            return api_get(auth, ctx, params)
        except ApiError as e:
            if "lastupdt" in str(e).lower() and _date_fmt["mode"] == "short":
                _date_fmt["mode"] = "long"
                continue
            raise
    raise ApiError("lastupdt rejected in both short and long format")


def box_total(auth, ctx, lat1, lat2, lon1, lon2, since):
    data = query(auth, ctx, lat1, lat2, lon1, lon2, since, per_page=1)
    if "totalResults" not in data:
        raise ApiError("Response had no totalResults field. Keys: %s" % sorted(data.keys()))
    return int(data["totalResults"])


# ------------------------------------------------------------------- cache
def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            sys.exit("Cache file is damaged (%s). Rename or delete %s and re-run." % (e, CACHE_PATH))
    return {"version": 1, "entries": {}}


def save_cache(cache):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_PATH)


def ckey(since, i0, j0, n):
    return "%s|%d|%d|%d" % (since, i0, j0, n)


# ------------------------------------------------------------------- boxes
def read_cells_file(path):
    cells = set()
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or "i" not in rd.fieldnames or "j" not in rd.fieldnames:
            sys.exit("--cells file needs header columns i and j")
        for row in rd:
            try:
                cells.add((int(float(row["i"])), int(float(row["j"]))))
            except (ValueError, TypeError):
                continue
    return cells


def plan_boxes(bbox, n, cells_filter):
    s, w, nn, e = bbox
    i_lo, i_hi = cell_index(s), cell_index(nn)
    j_lo, j_hi = cell_index(w), cell_index(e)
    blocks = set()
    for i in range(i_lo, i_hi + 1):
        for j in range(j_lo, j_hi + 1):
            if cells_filter is not None and (i, j) not in cells_filter:
                continue
            blocks.add(((i // n) * n, (j // n) * n))
    clat, clon = (s + nn) / 2.0, (w + e) / 2.0

    def dist(b):
        lat = (b[0] + n / 2.0) * CELL
        lon = (b[1] + n / 2.0) * CELL
        return (lat - clat) ** 2 + ((lon - clon) * math.cos(math.radians(clat))) ** 2

    return sorted(blocks, key=dist)


def bbox_from_args(args):
    if args.bbox:
        s, w, n, e = args.bbox
        if not (s < n and w < e):
            sys.exit("--bbox is S W N E with S<N and W<E")
        return (s, w, n, e)
    if args.center:
        lat, lon = args.center
        dlat = args.radius_km / 111.0
        dlon = args.radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
        return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)
    return None


# --------------------------------------------------------------------- CSV
def build_csv(cache, since):
    cells = {}
    ents = [v for k, v in cache["entries"].items() if k.split("|")[0] == since]
    ents.sort(key=lambda v: -v["n"])  # big boxes first, finer boxes overwrite
    for v in ents:
        n = v["n"]
        per = float(v["total"]) / float(n * n)
        for di in range(n):
            for dj in range(n):
                cells[(v["i0"] + di, v["j0"] + dj)] = per
    rows = sorted(cells.items())
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["i", "j", "lat", "lon", "wifi_recent"])
        for (i, j), val in rows:
            wr.writerow([i, j, "%.4f" % ((i + 0.5) * CELL), "%.4f" % ((j + 0.5) * CELL), "%.2f" % val])
    os.replace(tmp, OUT_PATH)
    return len(rows), len(ents)


# --------------------------------------------------------------------- run
def run_queries(auth, ctx, cache, since, work, args):
    """work = list of (i0, j0, n). Returns (done_now, stopped_reason)."""
    done = 0
    for (i0, j0, n) in work:
        key = ckey(since, i0, j0, n)
        if key in cache["entries"]:
            continue
        if done >= args.max_queries:
            return done, "reached --max-queries %d" % args.max_queries
        lat1, lon1 = i0 * CELL, j0 * CELL
        lat2, lon2 = (i0 + n) * CELL - EPS, (j0 + n) * CELL - EPS
        try:
            total = box_total(auth, ctx, lat1, lat2, lon1, lon2, since)
        except LimitReached as e:
            return done, "daily limit: %s" % e
        cache["entries"][key] = {"i0": i0, "j0": j0, "n": n, "total": total}
        save_cache(cache)
        done += 1
        if done % 10 == 0:
            print("  %d queries done this run (last box total %d)" % (done, total))
        time.sleep(args.delay)
    return done, None


def cmd_run(args):
    since = valid_since(args.since or default_since())
    cache = load_cache()
    if args.build_only:
        nc, ne = build_csv(cache, since)
        print("Rebuilt %s: %d cells from %d cached boxes (cutoff %s)." % (OUT_PATH, nc, ne, since))
        return
    auth = load_auth()  # creates wigle_config.json on first run if missing
    bbox = bbox_from_args(args)
    if bbox is None and not args.refine_top:
        sys.exit("Credentials found. Now give an area: --center LAT LON --radius-km KM   or   --bbox S W N E")
    n = max(1, args.box_cells)
    cells_filter = read_cells_file(args.cells) if args.cells else None
    ctx = ssl_context()

    total_done = 0
    reason = None
    try:
        if bbox is not None:
            boxes = plan_boxes(bbox, n, cells_filter)
            todo = [b for b in boxes if ckey(since, b[0], b[1], n) not in cache["entries"]]
            print("Cutoff %s. %d boxes of %dx%d cells planned, %d already cached, %d to query."
                  % (since, len(boxes), n, n, len(boxes) - len(todo), len(todo)))
            d, reason = run_queries(auth, ctx, cache, since, [(b[0], b[1], n) for b in boxes], args)
            total_done += d
        if reason is None and args.refine_top:
            cands = [v for k, v in cache["entries"].items()
                     if k.split("|")[0] == since and v["n"] > 1 and v["total"] >= args.refine_min]
            cands.sort(key=lambda v: -v["total"])
            cands = cands[:args.refine_top]
            work = []
            for v in cands:
                for di in range(v["n"]):
                    for dj in range(v["n"]):
                        work.append((v["i0"] + di, v["j0"] + dj, 1))
            pending = [w for w in work if ckey(since, w[0], w[1], 1) not in cache["entries"]]
            print("Refine: %d dense boxes, %d single-cell queries pending." % (len(cands), len(pending)))
            d, reason = run_queries(auth, ctx, cache, since, work, args)
            total_done += d
    except AuthError as e:
        save_cache(cache)
        sys.exit("\nSTOPPED - %s" % e)
    except ApiError as e:
        save_cache(cache)
        sys.exit("\nSTOPPED - %s\nProgress is saved; re-run the same command." % e)

    nc, ne = build_csv(cache, since)
    print("\n%d queries this run." % total_done)
    if reason:
        print("Stopped early: %s" % reason)
        print("Progress is saved. Run the same command again later (daily limits reset) to continue.")
    else:
        print("All planned boxes finished.")
    print("Wrote %s" % OUT_PATH)
    print("  %d cells from %d cached boxes (cutoff %s)" % (nc, ne, since))
    print("Next: upload wigle_density.csv in the planner page, \"Recent WiGLE density\" card.")


# -------------------------------------------------------------------- test
def cmd_test(args):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    since = valid_since(args.since or default_since())
    t = datetime.date.today()
    one_year = "%04d%02d%02d" % (t.year - 1, t.month, 1)
    lat, lon = args.test_center if args.test_center else (42.3601, -71.0589)
    i0, j0 = (cell_index(lat) // 3) * 3, (cell_index(lon) // 3) * 3
    s, w = i0 * CELL, j0 * CELL
    nn, e = (i0 + 3) * CELL - EPS, (j0 + 3) * CELL - EPS
    mid = (w + e) / 2.0

    out("WiGLE density diagnostic - %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    out("Python %s" % sys.version.split()[0])
    out("API url: %s" % API_URL)
    out("Test box (3x3 cells): lat %.4f..%.4f lon %.4f..%.4f" % (s, nn, w, e))
    out("default cutoff %s, 1-year cutoff %s" % (since, one_year))
    out()
    auth = load_auth()
    ctx = ssl_context()
    res = {}

    def step(name, fn):
        try:
            res[name] = fn()
            out("%-34s %s" % (name, res[name]))
        except (AuthError, LimitReached, ApiError) as ex:
            res[name] = None
            out("%-34s FAILED: %s" % (name, ex))
            if isinstance(ex, (AuthError, LimitReached)):
                raise

    try:
        step("T1 total, no lastupdt filter", lambda: box_total(auth, ctx, s, nn, w, e, None))
        time.sleep(args.delay)
        step("T2 total, lastupdt cutoff", lambda: box_total(auth, ctx, s, nn, w, e, since))
        time.sleep(args.delay)
        step("T3 total, lastupdt 1y", lambda: box_total(auth, ctx, s, nn, w, e, one_year))
        time.sleep(args.delay)
        step("T4a total, west half, cutoff", lambda: box_total(auth, ctx, s, nn, w, mid, since))
        time.sleep(args.delay)
        step("T4b total, east half, cutoff", lambda: box_total(auth, ctx, s, nn, mid + EPS, e, since))
        time.sleep(args.delay)
        step("T5 single cell, cutoff", lambda: box_total(auth, ctx, s, s + CELL - EPS, w, w + CELL - EPS, since))
        time.sleep(args.delay)

        def sample():
            d = query(auth, ctx, s, nn, w, e, since, per_page=5)
            rs = d.get("results") or []
            lu = sorted(str(r.get("lastupdt", ""))[:10] for r in rs)
            return "%d records, lastupdt values: %s" % (len(rs), ", ".join(lu) if lu else "(none)")
        step("T6 sample records (lastupdt)", sample)
        sample_text = res.get("T6 sample records (lastupdt)")
    except (AuthError, LimitReached):
        out()
        out("Stopped: account problem or limit. See the FAILED line above.")
        _write_report(lines)
        return

    out()
    out("lastupdt format that worked: %s" % ("yyyyMMdd" if _date_fmt["mode"] == "short" else "yyyyMMddhhmmss"))
    out("Checks:")
    t1, t2, t3 = res.get("T1 total, no lastupdt filter"), res.get("T2 total, lastupdt cutoff"), res.get("T3 total, lastupdt 1y")
    a, b = res.get("T4a total, west half, cutoff"), res.get("T4b total, east half, cutoff")
    if None not in (t1, t2, t3):
        out("  filter shrinks count (T3<=T2<=T1): %s" % ("PASS" if t3 <= t2 <= t1 else "FAIL"))
        out("  filter actually changes something (T2<T1): %s" % ("PASS" if t2 < t1 else "NOTE - equal; try a box with older networks"))
    if None not in (t2, a, b):
        diff = abs((a + b) - t2)
        ok = diff <= max(3, 0.02 * t2)
        out("  halves add up to whole (%d + %d vs %d): %s" % (a, b, t2, "PASS" if ok else "FAIL - totals may be capped or unreliable"))
    if t1 is not None and t1 in (1000, 10000, 100000):
        out("  WARNING: T1 is a round number (%d), totalResults may be capped." % t1)
    out()
    out("Report saved to: %s" % REPORT_PATH)
    out("It contains no credentials, so it is safe to share when asking for help.")
    _write_report(lines)


def _write_report(lines):
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Recent WiGLE WiFi density per 2 km cell",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="See the top of this file for full instructions.")
    ap.add_argument("--test", action="store_true", help="run the diagnostic and write wigle_test_report.txt")
    ap.add_argument("--test-center", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--center", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--radius-km", type=float, default=40.0)
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("S", "W", "N", "E"))
    ap.add_argument("--box-cells", type=int, default=3)
    ap.add_argument("--refine-top", type=int, default=0)
    ap.add_argument("--refine-min", type=int, default=150, help="only refine boxes with at least this many networks")
    ap.add_argument("--since", type=str, default=None)
    ap.add_argument("--max-queries", type=int, default=400)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--cells", type=str, default=None)
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    if args.test:
        cmd_test(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved in the cache; re-run to continue.")
