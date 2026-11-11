#!/usr/bin/env python3
"""
preflight.py - every check in the pack, on one draft, with one verdict.

The pack has a counter, a humanizer panel and a voice check, and each one is
easy to forget. This runs all of them on the same text and prints a single
READY or FIX FIRST, with the fixes in the order that matters:

  COUNT   li-post/count.py   limits, the fold, links, hashtags, bait, walls
  HUMAN   li-human/detect.py the five-check detection panel
  VOICE   li-voice/voice.py  drift from your measured voice, if a profile exists

It changes nothing. Run the humanizer first if HUMAN fails.

Usage
  python3 preflight.py draft.txt
  python3 preflight.py comment.txt --kind comment
  python3 preflight.py draft.txt --profile ~/.claude/linkedin/voice.json --json

Exit 0 when READY, 1 when something needs fixing, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("li-post", "li-human", "li-voice"):
    sys.path.insert(0, os.path.join(HERE, "..", sub))

import count      # noqa: E402
import detect     # noqa: E402
import voice      # noqa: E402

DEFAULT_PROFILE = os.path.expanduser("~/.claude/linkedin/voice.json")


def run(text: str, kind: str = "post", profile_path: Optional[str] = None) -> Dict[str, Any]:
    stages: List[Dict[str, Any]] = []
    fixes: List[str] = []

    c = count.analyse(text, kind)
    fails = [x for x in c["checks"] if x["status"] == "FAIL"]
    warns = [x for x in c["checks"] if x["status"] == "WARN"]
    stages.append({"stage": "COUNT", "status": "FAIL" if fails else "WARN" if warns else "PASS",
                   "detail": f"{c['characters']:,} / {c['limit']:,}" + (f", {len(warns)} warning(s)" if warns else "")})
    fixes += [f"{x['check']}: {x['detail']}" for x in fails + warns]

    with open(detect.LEX, encoding="utf-8") as fh:
        lex = json.load(fh)
    results, overall, verdict = detect.run(text, lex)
    stages.append({"stage": "HUMAN", "status": "PASS" if verdict == "PASS" else "WARN" if verdict == "REVIEW" else "FAIL",
                   "detail": f"{overall:.1f} {verdict}"})
    if verdict != "PASS":
        weakest = min(detect.CHECKS, key=lambda k: results[k][0] if results[k][0] is not None else 999)
        fixes.append(f"HUMAN: weakest signal is {weakest}. Run humanize.py, then rewrite the flagged lines.")

    path = profile_path or (DEFAULT_PROFILE if os.path.exists(DEFAULT_PROFILE) else None)
    if path:
        try:
            with open(os.path.expanduser(path), encoding="utf-8") as fh:
                prof = json.load(fh)
            v = voice.check(prof, text)
            stages.append({"stage": "VOICE", "status": "PASS" if v["verdict"] == "MATCH" else
                           "WARN" if v["verdict"] == "CLOSE" else "FAIL", "detail": f"{v['score']:.1f} {v['verdict']}"})
            fixes += [f"VOICE: {h}" for h in v["hard"]]
        except (OSError, ValueError, KeyError) as e:
            stages.append({"stage": "VOICE", "status": "SKIP", "detail": f"profile unreadable: {e}"})
    else:
        stages.append({"stage": "VOICE", "status": "SKIP",
                       "detail": "no profile. Run /li-voice once to measure yours."})

    ready = not any(s["status"] == "FAIL" for s in stages)
    return {"kind": kind, "ready": ready, "stages": stages, "fixes": fixes}


def render(r: Dict[str, Any], out=sys.stdout) -> None:
    print(f"\nPRE-FLIGHT  ·  {r['kind']}", file=out)
    print("=" * 60, file=out)
    for s in r["stages"]:
        print(f"  {s['stage']:<6} {s['status']:<5} {s['detail']}", file=out)
    print("-" * 60, file=out)
    print(f"  {'READY' if r['ready'] else 'FIX FIRST'}", file=out)
    for i, f in enumerate(r["fixes"], 1):
        print(f"  {i}. {f}", file=out)
    print("", file=out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run every check on one draft.")
    ap.add_argument("input", nargs="?", default="-")
    ap.add_argument("--kind", choices=sorted(count.LIMITS), default="post")
    ap.add_argument("--profile", help="voice profile JSON (default: ~/.claude/linkedin/voice.json if it exists)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.input == "-":
            text = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8") as fh:
                text = fh.read()
    except OSError as e:
        print(f"could not read input: {e}", file=sys.stderr)
        return 2
    if not text.strip():
        print("nothing to check", file=sys.stderr)
        return 2
    r = run(text, args.kind, args.profile)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        render(r)
    return 0 if r["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
