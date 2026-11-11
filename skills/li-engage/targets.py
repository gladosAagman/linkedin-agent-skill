#!/usr/bin/env python3
"""
targets.py - the engagement ledger. Who you replied to, how often, and who
you have gone quiet on.

On LinkedIn, engaging with other people's posts is how a small account
grows, and the plan in this pack splits it 5 reach / 3 peers / 2 buyers. Two
things go wrong without a record: you drift onto the same three people every
day (which is visible, and looks like what it is), and the buyers you meant
to warm up for weeks get forgotten after day four. This keeps the record. It
is a plain CSV on your machine. It never opens LinkedIn and it never posts.

Usage
  python3 targets.py add "Sarah Chen" --tier reach --note "added the churn number"
  python3 targets.py add "Sarah Chen" --tier peer --date 2026-09-29
  python3 targets.py report                    # last 7 days: concentration, tier mix, gaps
  python3 targets.py report --days 14 --json
  python3 targets.py due --roster roster.txt   # who on your list you have not touched lately

The roster is one person per line, optionally "name,tier". The ledger lives
at ~/.claude/linkedin/engage.csv unless you pass --ledger.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

DEFAULT_LEDGER = os.path.expanduser("~/.claude/linkedin/engage.csv")
TIERS = ("reach", "peer", "buyer")
TARGET_MIX = {"reach": 0.5, "peer": 0.3, "buyer": 0.2}
FIELDS = ["date", "who", "tier", "note"]
HANDLE_MODE = False          # True: X handles. False: free-text names.
HANDLE_RE = re.compile(r"^@?([A-Za-z0-9_]{1,15})$")
STALE_DAYS = 14
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def normalise_who(raw: str) -> str:
    """Canonical key for a person. Raises ValueError on input that is not one."""
    raw = (raw or "").strip()
    if HANDLE_MODE:
        m = HANDLE_RE.match(raw)
        if not m:
            raise ValueError(f"{raw!r} is not an X handle (letters, digits, _ and at most 15)")
        return m.group(1).lower()
    name = re.sub(r"\s+", " ", raw)
    if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError("a name is 1 to 80 printable characters")
    return name


def display(who: str) -> str:
    return f"@{who}" if HANDLE_MODE else who


def key(who: str) -> str:
    return who.lower()


def safe_cell(text: str) -> str:
    """Stop a note pasted from someone else's post being read as a spreadsheet
    formula when the ledger is opened in Excel or Sheets."""
    text = (text or "").replace("\r", " ").replace("\n", " ").strip()
    return "'" + text if text.startswith(FORMULA_START) else text


def unsafe_cell(text: str) -> str:
    return text[1:] if text.startswith("'") and text[1:2] in FORMULA_START else text


def read_ledger(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                d = date.fromisoformat((r.get("date") or "").strip())
                who = normalise_who(unsafe_cell(r.get("who") or ""))
            except ValueError:
                continue                     # a hand-edited bad row is skipped, not fatal
            tier = (r.get("tier") or "").strip().lower()
            rows.append({"date": d.isoformat(), "who": who, "tier": tier if tier in TIERS else "",
                         "note": unsafe_cell(r.get("note") or "")})
    return rows


def append(path: str, row: Dict[str, str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date": row["date"], "who": safe_cell(row["who"]), "tier": row["tier"],
                    "note": safe_cell(row["note"])})


def report(rows: List[Dict[str, str]], days: int, today: Optional[date] = None) -> Dict[str, object]:
    today = today or date.today()
    since = today - timedelta(days=days - 1)
    window = [r for r in rows if since <= date.fromisoformat(r["date"]) <= today]
    per: Dict[str, Dict[str, object]] = {}
    for r in window:
        p = per.setdefault(key(r["who"]), {"who": r["who"], "n": 0, "tier": r["tier"]})
        p["n"] = int(p["n"]) + 1
        if r["tier"]:
            p["tier"] = r["tier"]
    ranked = sorted(per.values(), key=lambda p: (-int(p["n"]), str(p["who"]).lower()))
    total = len(window)
    top3 = sum(int(p["n"]) for p in ranked[:3])
    tiers = {t: sum(1 for r in window if r["tier"] == t) for t in TIERS}
    tiered = sum(tiers.values())
    mix = {t: (tiers[t] / tiered if tiered else 0.0) for t in TIERS}
    warnings = []
    if total >= 10 and len(ranked) > 3 and top3 / total > 0.5:
        warnings.append(f"{top3 / total:.0%} of your engagement went to 3 people. That is visible. Rotate.")
    if total >= 10 and len(ranked) <= 3:
        warnings.append(f"{total} interactions across only {len(ranked)} people. Widen the list.")
    if tiered >= 10:
        for t in TIERS:
            if mix[t] < TARGET_MIX[t] / 2:
                warnings.append(f"{t} is {mix[t]:.0%} of the mix against a target of {TARGET_MIX[t]:.0%}.")
    active = len({r["date"] for r in window})
    return {"days": days, "since": since.isoformat(), "total": total, "people": len(ranked),
            "active_days": active, "top3_share": round(top3 / total, 3) if total else 0.0,
            "tiers": tiers, "mix": {t: round(v, 3) for t, v in mix.items()}, "ranked": ranked,
            "warnings": warnings}


def read_roster(path: str) -> List[Tuple[str, str]]:
    out, seen = [], set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, tier = line.partition(",")
            try:
                who = normalise_who(name)
            except ValueError:
                print(f"  skipped roster line {line!r}: not a valid entry", file=sys.stderr)
                continue
            if key(who) in seen:
                continue
            seen.add(key(who))
            tier = tier.strip().lower()
            out.append((who, tier if tier in TIERS else ""))
    return out


def due(rows: List[Dict[str, str]], roster: List[Tuple[str, str]], today: Optional[date] = None):
    today = today or date.today()
    last: Dict[str, date] = {}
    for r in rows:
        d = date.fromisoformat(r["date"])
        k = key(r["who"])
        if k not in last or d > last[k]:
            last[k] = d
    out = []
    for who, tier in roster:
        d = last.get(key(who))
        out.append({"who": who, "tier": tier, "last": d.isoformat() if d else None,
                    "days": (today - d).days if d else None})
    out.sort(key=lambda r: (-(10 ** 6) if r["days"] is None else -r["days"], r["who"].lower()))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="The engagement ledger.")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="log one interaction")
    a.add_argument("who")
    a.add_argument("--tier", choices=TIERS, required=True)
    a.add_argument("--note", default="")
    a.add_argument("--date", help="YYYY-MM-DD, default today")
    r = sub.add_parser("report", help="the last N days")
    r.add_argument("--days", type=int, default=7)
    r.add_argument("--json", action="store_true")
    d = sub.add_parser("due", help="who on the roster has gone quiet")
    d.add_argument("--roster", required=True)
    d.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "add":
        try:
            who = normalise_who(args.who)
            when = date.fromisoformat(args.date) if args.date else date.today()
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        if when > date.today():
            print("that date is in the future", file=sys.stderr)
            return 2
        append(args.ledger, {"date": when.isoformat(), "who": who, "tier": args.tier, "note": args.note[:280]})
        print(f"logged {display(who)} ({args.tier}) on {when.isoformat()}")
        return 0

    rows = read_ledger(args.ledger)
    if args.cmd == "report":
        if not 1 <= args.days <= 366:
            print("--days must be between 1 and 366", file=sys.stderr)
            return 2
        rep = report(rows, args.days)
        if args.json:
            print(json.dumps(rep, indent=2))
            return 0
        print(f"\nENGAGEMENT  ·  last {rep['days']} days  ·  {rep['total']} interactions  ·  "
              f"{rep['people']} people  ·  {rep['active_days']} active days")
        print("=" * 72)
        if not rep["total"]:
            print("  nothing logged in this window. Log each reply with `targets.py add`.\n")
            return 0
        t, m = rep["tiers"], rep["mix"]
        print(f"  mix   reach {t['reach']} ({m['reach']:.0%})   peer {t['peer']} ({m['peer']:.0%})   "
              f"buyer {t['buyer']} ({m['buyer']:.0%})    target 50 / 30 / 20")
        print(f"  top 3 people took {rep['top3_share']:.0%} of it\n")
        for p in rep["ranked"][:12]:
            print(f"    {int(p['n']):3d}  {display(str(p['who'])):<28} {p['tier']}")
        for w in rep["warnings"]:
            print(f"\n  WARN  {w}")
        print("")
        return 0

    try:
        roster = read_roster(args.roster)
    except OSError as e:
        print(f"could not read roster: {e}", file=sys.stderr)
        return 2
    rows_due = due(rows, roster)
    if args.json:
        print(json.dumps(rows_due, indent=2))
        return 0
    print(f"\nDUE  ·  {len(rows_due)} on the roster, most overdue first\n")
    for r in rows_due:
        when = "never" if r["days"] is None else f"{r['days']}d ago"
        flag = "  <- overdue" if r["days"] is None or r["days"] > STALE_DAYS else ""
        print(f"    {when:>9}  {display(r['who']):<28} {r['tier']}{flag}")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
