#!/usr/bin/env python3
"""
audit.py - read your own LinkedIn post analytics and say what actually
worked, with the sample size attached to every claim.

Third-party LinkedIn analytics tools keep disappearing, and reach has moved
enough in the last two years that last year's rules are guesses. Your own
export is the one source that cannot go dark. This reads it locally.

Input, any of:
  - the Content export from LinkedIn analytics (.xlsx). It holds several
    sheets; this finds the one with an Impressions column, or use --sheet.
    The "top posts" sheet puts two tables side by side (by engagement and by
    impressions); they are merged on the post URL.
  - the same sheet saved as CSV
  - a sheet you made by hand: post text (or URL), impressions, and whatever
    of reactions / comments / reposts / saves / sends you can see

Columns are matched loosely ("Impressions", "impressions", "Post impressions"
all work). LinkedIn does not document them and they change.

What it computes per post, and why not raw impressions: impressions mostly
measure how many people already follow you.

  engagement rate   (reactions + comments + reposts) / impressions,
                    or the Engagements column when the export has one
  comment ratio     comments / reactions: started something, or got a nod
  saves+sends /1k   the "I will use this" and "you need to see this" signals
  reach multiple    impressions / followers (pass --followers)

Then it groups posts by what it can see (length, a link in the body, hashtag
count, the format column, the first line ending in a question) and reports
every group 1.4x above or below the rest with its n. Day of week is checked
last, on purpose.

Usage
  python3 audit.py Content_2026-09-01_2026-09-30.xlsx
  python3 audit.py posts.csv --followers 4200
  python3 audit.py export.xlsx --sheet "TOP POSTS" --json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

FIELDS: Dict[str, List[str]] = {
    "text":        ["post commentary", "post text", "commentary", "text", "content", "post title"],
    "link":        ["post url", "post link", "url", "link", "permalink"],
    "date":        ["post publish date", "publish date", "created date", "date", "published"],
    "impressions": ["impressions", "views"],
    "engagements": ["engagements"],
    "reactions":   ["reactions", "likes"],
    "comments":    ["comments"],
    "reposts":     ["reposts", "shares"],
    "saves":       ["saves"],
    "sends":       ["sends"],
    "clicks":      ["clicks"],
    "format":      ["post type", "content type", "media type", "format", "type"],
}
NUMERIC = ("impressions", "engagements", "reactions", "comments", "reposts", "saves", "sends", "clicks")
DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M",
                "%Y-%m-%dT%H:%M:%S", "%d %b %Y"]
URL_RE = re.compile(r"https?://\S+|\b[a-z0-9-]+\.(?:com|io|ai|co|net|org|dev|app)\b", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(?:^|(?<=\s))#[A-Za-z]\w*")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
MAX_MEMBER_BYTES = 50 * 1024 * 1024        # refuse decompression bombs
MAX_ROWS = 20000


# ---------------------------------------------------------------- reading

def norm(h: Any) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(h or "").lower()).strip()


def _xlsx_member(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{name} unpacks to {info.file_size:,} bytes; refusing")
    return z.read(name)


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(path: str, sheet: Optional[str] = None) -> Dict[str, List[List[str]]]:
    """Every sheet as a list of rows of strings. Standard library only.
    ElementTree does not resolve external entities, and member sizes are
    capped, so a hostile file cannot reach the network or fill the disk."""
    out: Dict[str, List[List[str]]] = {}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(_xlsx_member(z, "xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        wb = ET.fromstring(_xlsx_member(z, "xl/workbook.xml"))
        rels = ET.fromstring(_xlsx_member(z, "xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels.findall("rel:Relationship", NS)}
        for s in wb.findall("m:sheets/m:sheet", NS):
            name = s.get("name") or ""
            if sheet and name.strip().lower() != sheet.strip().lower():
                continue
            t = target.get(s.get(f"{{{NS['r']}}}id"), "")
            t = t.lstrip("/")
            member = t if t.startswith("xl/") else "xl/" + t
            if member not in names:
                continue
            root = ET.fromstring(_xlsx_member(z, member))
            rows: List[List[str]] = []
            for row in root.iter(f"{{{NS['m']}}}row"):
                cells: Dict[int, str] = {}
                for c in row.findall("m:c", NS):
                    ref, typ = c.get("r") or "", c.get("t")
                    v = c.find("m:v", NS)
                    if typ == "s" and v is not None and v.text is not None and v.text.isdigit():
                        i = int(v.text)
                        val = shared[i] if i < len(shared) else ""
                    elif typ == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    else:
                        val = v.text if v is not None and v.text is not None else ""
                    idx = _col_index(ref) if ref else len(cells)
                    cells[idx] = val
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
                if len(rows) > MAX_ROWS:
                    raise ValueError(f"sheet {name!r} has more than {MAX_ROWS:,} rows")
            out[name] = rows
    if sheet and not out:
        raise ValueError(f"no sheet named {sheet!r}")
    return out


def read_csv(path: str) -> List[List[str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [r for _, r in zip(range(MAX_ROWS + 1), csv.reader(fh))]


def map_columns(header: List[str]) -> Dict[str, int]:
    h = [norm(x) for x in header]
    out: Dict[str, int] = {}
    for field, names in FIELDS.items():
        for name in names:
            if name in h and h.index(name) not in out.values():
                out[field] = h.index(name)
                break
        else:
            for i, col in enumerate(h):
                if col and i not in out.values() and any(col.startswith(n) or col.endswith(n) for n in names):
                    out[field] = i
                    break
    return out


def header_row(rows: List[List[str]]) -> Optional[int]:
    for i, r in enumerate(rows[:30]):
        if any(norm(c) in ("impressions", "views") or norm(c).endswith("impressions") for c in r):
            return i
    return None


def segments(header: List[str]) -> List[Tuple[int, int]]:
    """Side-by-side tables separated by an empty header cell."""
    segs, start = [], None
    for i, c in enumerate(header + [""]):
        if str(c).strip() and start is None:
            start = i
        elif not str(c).strip() and start is not None:
            segs.append((start, i))
            start = None
    return segs


def to_num(v: Any) -> Optional[float]:
    s = str(v or "").strip().replace(",", "").replace("%", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None          # "nan" and "inf" parse as floats; they are not data


def parse_date(v: Any) -> Optional[datetime]:
    s = str(v or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", s):              # an Excel serial date
        try:
            return datetime(1899, 12, 30) + timedelta(days=float(s))
        except (OverflowError, ValueError):
            return None
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def table_posts(rows: List[List[str]]) -> List[Dict[str, Any]]:
    hi = header_row(rows)
    if hi is None:
        return []
    header, body = rows[hi], rows[hi + 1:]
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for a, b in segments(header) or [(0, len(header))]:
        cols = map_columns(header[a:b])
        if not cols:
            continue
        for n, raw in enumerate(body):
            seg = raw[a:b]
            get = lambda f: seg[cols[f]] if f in cols and cols[f] < len(seg) else ""
            if not any(str(x).strip() for x in seg):
                continue
            k = str(get("link")).strip() or f"row{n}"
            p = merged.get(k)
            if p is None:
                p = {"text": "", "link": "", "date": None, "format": ""}
                merged[k] = p
                order.append(k)
            for f in NUMERIC:
                v = to_num(get(f))
                if v is not None and p.get(f) is None:
                    p[f] = v
            p["text"] = p["text"] or str(get("text")).strip()
            p["link"] = p["link"] or str(get("link")).strip()
            p["format"] = p["format"] or str(get("format")).strip().lower()
            p["date"] = p["date"] or parse_date(get("date"))
    return [merged[k] for k in order if merged[k].get("impressions")]


def load(path: str, sheet: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    if path.lower().endswith((".xlsx", ".xlsm")):
        sheets = read_xlsx(path, sheet)
        best: Tuple[List[Dict[str, Any]], str] = ([], "")
        for name, rows in sheets.items():
            posts = table_posts(rows)
            if len(posts) > len(best[0]):
                best = (posts, name)
        return best
    return table_posts(read_csv(path)), "csv"


# ---------------------------------------------------------------- analysis

def derive(p: Dict[str, Any], followers: Optional[int]) -> Dict[str, Any]:
    imp = p["impressions"]
    parts = [p.get(k) or 0 for k in ("reactions", "comments", "reposts")]
    eng = p["engagements"] if p.get("engagements") is not None else sum(parts)
    p["er"] = eng / imp if imp else 0.0
    p["comment_ratio"] = (p.get("comments") or 0) / max(p.get("reactions") or 0, 1)
    p["saves_sends_1k"] = ((p.get("saves") or 0) + (p.get("sends") or 0)) * 1000 / imp if imp else 0.0
    p["reach_multiple"] = imp / followers if followers else None
    t = p.get("text") or ""
    p["hook"] = next((ln.strip() for ln in t.splitlines() if ln.strip()), "") or p.get("link", "")
    if t:
        n = len(t)
        p["length"] = ("under 400" if n < 400 else "400-899" if n < 900 else "900-1300" if n <= 1300
                       else "1301-2000" if n <= 2000 else "2000+")
        p["has_link"] = "link in body" if URL_RE.search(t) else "no link"
        tags = len(HASHTAG_RE.findall(t))
        p["hashtags"] = "0" if tags == 0 else "1-3" if tags <= 3 else "4+"
        p["hook_question"] = "line 1 is a question" if p["hook"].endswith("?") else "line 1 is a statement"
    else:
        p["length"] = p["has_link"] = p["hashtags"] = p["hook_question"] = None
    p["format"] = p.get("format") or None
    p["weekday"] = p["date"].strftime("%a") if p.get("date") else None
    return p


def findings(posts: List[Dict[str, Any]], key: str, label: str) -> List[Dict[str, Any]]:
    res = []
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in posts:
        if p.get(key) is not None:
            groups.setdefault(str(p[key]), []).append(p)
    for k, items in groups.items():
        rest = [p for p in posts if p.get(key) is not None and str(p[key]) != k]
        if len(items) < 3 or len(rest) < 3:
            continue
        a = statistics.mean(p["er"] for p in items)
        b = statistics.mean(p["er"] for p in rest)
        if b == 0:
            continue
        ratio = a / b
        if ratio >= 1.4 or ratio <= 0.7:
            res.append({"dimension": label, "group": k, "n": len(items), "mean_er": a, "rest_er": b,
                        "ratio": ratio})
    if len(groups) == 2 and len(res) == 2:
        res = [max(res, key=lambda f: f["ratio"])]
    return res


def confidence(n: int) -> str:
    return "solid" if n >= 10 else "moderate" if n >= 5 else "weak"


def pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def analyse(posts: List[Dict[str, Any]], followers: Optional[int], floor: Optional[int]) -> Dict[str, Any]:
    posts = [derive(p, followers) for p in posts]
    imps = sorted(p["impressions"] for p in posts)
    fl = floor if floor is not None else max(50, int(imps[len(imps) // 10]) if len(imps) >= 10 else 50)
    ranked = sorted([p for p in posts if p["impressions"] >= fl], key=lambda p: -p["er"])
    dims = [("format", "format"), ("length", "length"), ("has_link", "link"), ("hashtags", "hashtags"),
            ("hook_question", "first line")]
    found: List[Dict[str, Any]] = []
    for k, label in dims:
        found += findings(ranked, k, label)
    found.sort(key=lambda f: -abs(f["ratio"] - 1) * min(f["n"], 10))
    days = findings(ranked, "weekday", "day of week")
    return {"posts": posts, "ranked": ranked, "floor": fl, "findings": found, "days": days}


def render(a: Dict[str, Any], source: str, followers: Optional[int]) -> None:
    posts, ranked = a["posts"], a["ranked"]
    dates = [p["date"] for p in posts if p.get("date")]
    span = f"{min(dates):%b %d} - {max(dates):%b %d}" if dates else "dates unread"
    has_text = any(p.get("text") for p in posts)
    print(f"\nAUDIT  ·  {len(posts)} posts  ·  {span}  ·  from {source}")
    print("=" * 78)
    print(f"ranked by engagement rate, posts under {a['floor']:,.0f} impressions left out as noise\n")

    def row(p: Dict[str, Any]) -> str:
        hook = p["hook"] if len(p["hook"]) <= 42 else p["hook"][:39] + "..."
        reach = f"  {p['reach_multiple']:.2f}x reach" if p["reach_multiple"] is not None else ""
        return (f"  {pct(p['er']):>6}  {p['comment_ratio']:4.2f} c/r  {p['saves_sends_1k']:5.1f} sv+sd/1k  "
                f"{p['impressions']:>8,.0f} imp{reach}  \"{hook}\"")

    k = min(5, max(1, len(ranked) // 3))
    print("TOP BY ENGAGEMENT RATE")
    for p in ranked[:k]:
        print(row(p))
    print("\nBOTTOM")
    for p in ranked[-k:]:
        print(row(p))
    most_seen = max(posts, key=lambda p: p["impressions"])
    if ranked and most_seen is not ranked[0] and most_seen["impressions"] > ranked[0]["impressions"]:
        rank = next((i for i, p in enumerate(ranked, 1) if p is most_seen), None)
        where = f"#{rank} of {len(ranked)}" if rank else "below the noise floor"
        print(f"\n  Your most-seen post ranks {where} by engagement rate. Reach and resonance are not the same.")
    print("\nWHAT THE DATA SAYS")
    if len(ranked) < 12:
        print(f"  {len(ranked)} posts is too few for a pattern. Anything below is a hint, not a finding.")
    if not has_text:
        print("  The export has no post text, so length, links and hashtags cannot be checked. Add a text "
              "column by hand for the top and bottom five and re-run.")
    if not a["findings"]:
        print("  Nothing separates cleanly: no group is 1.4x above or below the rest with 3+ posts. Your topic "
              "and your first line matter more than any format lever here.")
    for i, f in enumerate(a["findings"][:5], 1):
        d = "above" if f["ratio"] > 1 else "below"
        print(f"  {i}. {f['dimension']} = {f['group']}: {pct(f['mean_er'])} vs {pct(f['rest_er'])} for everything "
              f"else ({f['ratio']:.1f}x, {d}). n={f['n']}, {confidence(f['n'])}.")
    if a["days"] and not a["findings"]:
        f = max(a["days"], key=lambda x: abs(x["ratio"] - 1))
        print(f"  Day of week: {f['group']} at {f['ratio']:.1f}x, n={f['n']}. Checked last on purpose. It is "
              "almost never the cause.")
    elif not a["days"]:
        print("  Day of week shows nothing. Stop optimising it.")
    if followers is None:
        print("\n  Pass --followers N to see the reach multiple: whether a post travelled past your own audience.")
    print("")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a LinkedIn post analytics export.")
    ap.add_argument("input", help=".xlsx or .csv")
    ap.add_argument("--sheet", help="sheet name inside an .xlsx")
    ap.add_argument("--followers", type=int, help="your follower count, for the reach multiple")
    ap.add_argument("--min-impressions", type=int, help="noise floor (default: 10th percentile, min 50)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.followers is not None and args.followers <= 0:
        print("--followers must be positive", file=sys.stderr)
        return 2
    try:
        posts, source = load(args.input, args.sheet)
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, KeyError) as e:
        print(f"could not read {args.input}: {e}", file=sys.stderr)
        return 2
    if not posts:
        print("no rows with impressions found. Is this the post-level export? Try --sheet, or save the sheet as "
              "CSV with a header row containing Impressions.", file=sys.stderr)
        return 2
    a = analyse(posts, args.followers, args.min_impressions)
    if args.json:
        clean = lambda p: {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in p.items()}
        print(json.dumps({"source": source, "posts": len(a["posts"]), "floor": a["floor"],
                          "ranked": [clean(p) for p in a["ranked"]], "findings": a["findings"],
                          "day_of_week": a["days"]}, indent=2, default=str))
        return 0
    render(a, source, args.followers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
