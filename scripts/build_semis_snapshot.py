"""Build semis/data/semis.json from a pipe-delimited scan dump.

Each input line: SYMBOL|Name|segment digit|last|pct_change|market_cap|volume
Segment digit is the last digit of the Morningstar industry code:
1 = equipment & materials (31130010), 2 = chips (31130020), 3 = solar (31130030).
pct_change is a ratio (0.012 = +1.2%).

Usage: python3 scripts/build_semis_snapshot.py dump.txt [--at ISO_TIME] > semis/data/semis.json
"""
import json, sys, datetime

SEG = {"1": "equipment", "2": "chips", "3": "solar"}

def num(s):
    s = s.strip()
    return None if s == "" else float(s)

def main():
    args = sys.argv[1:]
    at = None
    if "--at" in args:
        i = args.index("--at"); at = args[i + 1]; del args[i:i + 2]
    at = at or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows, seen = [], set()
    for ln in open(args[0], encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        p = ln.split("|")
        if len(p) != 7 or p[2] not in SEG:
            sys.exit(f"bad line: {ln}")
        if p[0] in seen:
            sys.exit(f"duplicate symbol: {p[0]}")
        seen.add(p[0])
        vol = num(p[6])
        rows.append({"symbol": p[0], "name": p[1], "seg": SEG[p[2]], "last": num(p[3]),
                     "pct_change": num(p[4]), "market_cap": num(p[5]),
                     "volume": None if vol is None else int(round(vol))})
    if len(rows) < 50:
        sys.exit(f"only {len(rows)} rows; refusing to write a short snapshot")
    json.dump({"updated": at, "source": "Robinhood market data (delayed)", "rows": rows}, sys.stdout, separators=(",", ":"))

main()
