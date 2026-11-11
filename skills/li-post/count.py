#!/usr/bin/env python3
"""
count.py - count and lint LinkedIn text the way the feed will treat it,
before you paste it in.

Five surfaces, five limits:

  post       3,000 characters. The feed cuts to "...see more" after about
             140 characters (or three lines) on mobile and about 210 on
             desktop, so line 1 is the only line most people read.
  comment    1,250 characters.
  invite     200 characters for a personalised connection note. Some
             Premium plans allow 300: pass --limit 300 if yours does.
  headline   220 characters.
  about      2,600 characters, with roughly the first two lines visible
             before "see more".

Characters are counted in UTF-16 units, the way a browser text box counts
them, so an emoji costs 2. That can over-count by a character or two next to
LinkedIn's own counter. It never under-counts, which is the direction that
matters when you are close to a limit.

The lints are the rules from /li-post, /li-comment, /li-dm and /li-profile:
the hook has to survive the fold, links go in the first comment, three
hashtags at most, no reflex bait, no wall of text, no em dash.

Usage
  python3 count.py post.txt
  python3 count.py comment.txt --kind comment
  python3 count.py note.txt --kind invite --limit 300
  python3 count.py --kind headline --text "Ops for 10-50 person agencies | cut proposal time 5h -> 20m"
  pbpaste | python3 count.py -
  python3 count.py post.txt --json

Exit code 0 when nothing FAILs, 1 when something does, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import unicodedata
from typing import Any, Dict, List, Optional

LIMITS = {"post": 3000, "comment": 1250, "invite": 200, "headline": 220, "about": 2600}
FOLD_MOBILE = 140
FOLD_DESKTOP = 210
FOLD_LINES = {"post": 3, "about": 2}
SWEET = (900, 1300)
HASHTAG_MAX = 3
PARAGRAPH_WALL = 300

URL_RE = re.compile(r"https?://\S+|(?<![@\w.])(?:www\.)?[a-z0-9-]+\.(?:com|io|ai|co|net|org|dev|app|ly|me|so)"
                    r"(?:/\S*)?\b", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(?:^|(?<=\s))#[A-Za-z][\w]*")
MENTION_RE = re.compile(r"(?:^|(?<=\s))@[A-Z][\w.-]+")
BAIT_RE = re.compile(r"(?i)(?:\b(?:thoughts|agree|who else|am i wrong|right)\?\s*$)"
                     r"|\bcomment\s+[\"'“]?\w+[\"'”]?\s+(?:below|if|and)\b"
                     r"|\b(?:like|repost|share) (?:this )?if\b"
                     r"|\bfollow (?:me )?for more\b")
COMMENT_OPENERS = re.compile(r"(?i)^\s*(?:great post|love this|so true|couldn'?t agree more|this resonates"
                             r"|well said|spot on|100%|facts|this!|[🔥👏💯🙌👆]+)")
HEADLINE_TELLS = re.compile(r"(?i)^\s*helping\b|\bpassionate\b|\bresults[- ]driven\b|\bguru\b|\bninja\b")
ABOUT_TELLS = re.compile(r"(?i)\bpassionate about\b|\bresults[- ]driven\b|\bseasoned professional\b"
                         r"|\bdynamic\b|\bself[- ]starter\b")


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def fold(text: str, kind: str, chars: int) -> str:
    """What shows before '...see more': the first `chars` characters or the
    first N lines, whichever comes first."""
    lines = text.splitlines()
    n = FOLD_LINES.get(kind, 3)
    head = "\n".join(lines[:n])
    if units(head) <= chars:
        return head
    out = ""
    for ch in head:
        if units(out + ch) > chars:
            break
        out += ch
    return out


def analyse(text: str, kind: str = "post", limit: Optional[int] = None) -> Dict[str, Any]:
    if kind not in LIMITS:
        raise ValueError(f"unknown kind {kind!r}")
    text = unicodedata.normalize("NFC", text.strip())
    limit = limit or LIMITS[kind]
    n = units(text)
    checks: List[Dict[str, str]] = []

    def add(status: str, name: str, msg: str) -> None:
        checks.append({"status": status, "check": name, "detail": msg})

    if n > limit:
        add("FAIL", "LENGTH", f"{n:,} / {limit:,}, {n - limit:,} over. LinkedIn will not take it.")
    elif kind == "post" and n < 400:
        add("WARN", "LENGTH", f"{n:,} characters. Under 400 reads as a thought, not a post. Fine if that is the point.")
    elif kind == "post" and n > 2000:
        add("WARN", "LENGTH", f"{n:,} characters. Over 2,000 has to earn every line, and line 2 has to pay for the tap.")
    elif kind == "post" and not SWEET[0] <= n <= SWEET[1]:
        add("NOTE", "LENGTH", f"{n:,} / {limit:,}. The working range for a text post is {SWEET[0]:,}-{SWEET[1]:,}.")
    else:
        add("PASS", "LENGTH", f"{n:,} / {limit:,}, {limit - n:,} left")

    hook = first_line(text)
    urls = [u.rstrip(".,;:!?)") for u in URL_RE.findall(text)]
    tags = HASHTAG_RE.findall(text)

    if kind in ("post", "about"):
        hn = units(hook)
        if hn > FOLD_MOBILE:
            add("WARN", "FIRST LINE", f"{hn} characters. Mobile cuts at about {FOLD_MOBILE}, so the point lands "
                "after \"see more\", for the few who tap.")
        else:
            add("PASS", "FIRST LINE", f"{hn} characters, survives the mobile fold")

    if kind == "post":
        if urls:
            add("WARN", "LINKS", f"{len(urls)} link(s) in the body. LinkedIn holds back posts that send people "
                "off the platform. Put the link in the first comment and say so in the post.")
        else:
            add("PASS", "LINKS", "none in the body")
        if len(tags) > HASHTAG_MAX:
            add("WARN", "HASHTAGS", f"{len(tags)}: {' '.join(tags[:6])}. Three at most, at the bottom, and only "
                "real categories someone follows.")
        else:
            add("PASS", "HASHTAGS", f"{len(tags)}" + (f": {' '.join(tags)}" if tags else ""))
        walls = [p for p in re.split(r"\n\s*\n", text) if units(p) > PARAGRAPH_WALL]
        if walls:
            add("WARN", "WALL", f"{len(walls)} paragraph(s) over {PARAGRAPH_WALL} characters. On a phone that is a "
                "grey block. One to three lines, then a blank line.")
        else:
            add("PASS", "WALL", "no paragraph over three phone lines")
        mentions = MENTION_RE.findall(text)
        if len(mentions) > 5:
            add("WARN", "TAGS", f"{len(mentions)} people tagged. Tagging people who will not engage reads as "
                "spam to them and to the feed. Tag the ones who are in the story.")
    if kind in ("post", "comment") and BAIT_RE.search(text):
        add("WARN", "BAIT", "reflex engagement bait (\"Thoughts?\", \"comment YES below\"). LinkedIn says it "
            "demotes engagement bait. Ask a question only this post could ask, or stop on the last true line.")
    if kind == "comment" and COMMENT_OPENERS.search(text):
        add("WARN", "OPENER", "opens on a stock compliment. It is invisible. Start on the specific thing.")
    if kind == "invite":
        if urls:
            add("WARN", "LINKS", "a link in an invite note reads as a funnel. Take it out.")
        if re.search(r"(?i)\b(?:call|demo|book|meeting|pitch|buy)\b", text):
            add("WARN", "ASK", "the note asks for something. The invite exists to make the accept obvious; "
                "the ask comes later, if at all.")
    if kind == "headline":
        if n < 60:
            add("NOTE", "ROOM", f"{n} characters of 220. A job title alone leaves the reader guessing who you help.")
        if HEADLINE_TELLS.search(text):
            add("WARN", "TELLS", "opens on \"Helping\" or uses passionate / results-driven. Every second headline "
                "does. Say who and what changes.")
    if kind == "about" and ABOUT_TELLS.search(fold(text, kind, FOLD_DESKTOP)):
        add("WARN", "TELLS", "the visible part of the about uses a stock phrase (passionate about, results-driven). "
            "Those two lines are the whole section for most readers.")

    em = text.count("—")
    if em:
        add("WARN", "EM DASH", f"{em}. Run it through /li-human before it goes anywhere.")

    return {
        "kind": kind, "characters": n, "limit": limit, "fits": n <= limit,
        "fold_mobile": fold(text, kind, FOLD_MOBILE) if kind in ("post", "about") else None,
        "fold_desktop": fold(text, kind, FOLD_DESKTOP) if kind in ("post", "about") else None,
        "links": urls, "hashtags": tags, "checks": checks,
    }


def render(a: Dict[str, Any], out=sys.stdout, width: int = 52) -> None:
    if a["fold_mobile"] is not None:
        print("\n  WHAT THE FEED SHOWS ON A PHONE, BEFORE \"...see more\"", file=out)
        print("  +" + "-" * (width + 2) + "+", file=out)
        for raw in a["fold_mobile"].split("\n"):
            for line in textwrap.wrap(raw, width) or [""]:
                print(f"  | {line:<{width}} |", file=out)
        tail = "...see more"
        print("  +" + "-" * (width - len(tail)) + f" {tail} " + "+", file=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<11} {c['detail']}", file=out)
    print("", file=out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Count and lint LinkedIn text.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("--kind", choices=sorted(LIMITS), default="post")
    ap.add_argument("--limit", type=int, help="override the limit (e.g. 300 for a Premium invite note)")
    ap.add_argument("--text", help="lint this string instead of a file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        print("--limit must be positive", file=sys.stderr)
        return 2
    try:
        if args.text is not None:
            raw = args.text
        elif args.input == "-":
            raw = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as e:
        print(f"could not read input: {e}", file=sys.stderr)
        return 2
    if not raw.strip():
        print("nothing to count", file=sys.stderr)
        return 2
    a = analyse(raw, args.kind, args.limit)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    return 0 if a["fits"] else 1


if __name__ == "__main__":
    sys.exit(main())
