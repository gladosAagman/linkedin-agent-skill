#!/usr/bin/env python3
"""
carousel.py - slide copy in, a linted 1080x1350 document post out.

Write the slides in a text file, one slide per block, separated by a line
containing only ---. The first line of a block is the headline; the rest is
the body. A leading "#" on the headline is ignored.

    # Proposals in 20 minutes
    The 6-step template we use now
    ---
    Why this matters
    Every hour on formatting is an hour not selling.
    ---
    ...

It lints the copy against /li-carousel's rules, then writes one HTML file
with one 1080x1350 page per slide, numbered, with your handle on every page.
Print it to PDF and upload that as a document post. With --pdf it finds
Chrome or Chromium and prints it for you; it never uploads anything.

Lints
  SLIDES     8 to 12. Under 8 is a text post; over 12, completion falls off.
  COVER      6 words or fewer on the cover headline.
  HEADLINE   3 to 7 words on every other headline.
  BODY       25 words or fewer under any headline. More is two slides.
  RECAP      the second-to-last slide should be the recap people screenshot.

Usage
  python3 carousel.py slides.txt --handle "@sarahchen" -o carousel.html
  python3 carousel.py slides.txt --handle "Sarah Chen" --accent "#0a66c2" --pdf carousel.pdf
  python3 carousel.py slides.txt --lint-only
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

W, H = 1080, 1350
MIN_SLIDES, MAX_SLIDES = 8, 12
COVER_WORDS, HEAD_MIN, HEAD_MAX, BODY_MAX = 6, 3, 7, 25
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")   # "- ", "* ", "• ", "1. ", "2) "
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def nwords(text: str) -> int:
    return len(re.findall(r"\S+", text))


def parse(text: str) -> List[Dict[str, str]]:
    slides = []
    for block in re.split(r"(?m)^\s*---\s*$", text):
        lines = [ln.rstrip() for ln in block.strip().splitlines()]
        lines = [ln for ln in lines if ln.strip()]
        if not lines:
            continue
        head = re.sub(r"^\s*#+\s*", "", lines[0]).strip()
        slides.append({"headline": head, "body": "\n".join(ln.strip() for ln in lines[1:])})
    return slides


def lint(slides: List[Dict[str, str]]) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    n = len(slides)
    if n < MIN_SLIDES:
        out.append(("WARN", "SLIDES", f"{n}. Under {MIN_SLIDES} is a text post with extra steps. Hand it to /li-post."))
    elif n > MAX_SLIDES:
        out.append(("WARN", "SLIDES", f"{n}. Past {MAX_SLIDES}, completion falls off. Cut or merge."))
    else:
        out.append(("PASS", "SLIDES", f"{n}"))
    for i, s in enumerate(slides, 1):
        hw, bw = nwords(s["headline"]), nwords(s["body"])
        if i == 1:
            if hw > COVER_WORDS:
                out.append(("WARN", "COVER", f"{hw} words. Six or fewer: the cover is 80% of the result."))
        elif not HEAD_MIN <= hw <= HEAD_MAX:
            out.append(("WARN", f"SLIDE {i}", f"headline is {hw} words; {HEAD_MIN} to {HEAD_MAX} reads at thumbnail size."))
        if bw > BODY_MAX:
            out.append(("WARN", f"SLIDE {i}", f"{bw} words of body. Over {BODY_MAX} is two slides."))
    if n >= 4:
        recap = slides[-2]["body"]
        if sum(1 for ln in recap.splitlines() if BULLET.match(ln)) < 2:
            out.append(("NOTE", "RECAP", "the second-to-last slide is not a list. The recap is the one people "
                        "screenshot; make it the whole carousel in one view."))
    if "—" in "".join(s["headline"] + s["body"] for s in slides):
        out.append(("WARN", "EM DASH", "run the copy through /li-human first."))
    return out


def render_html(slides: List[Dict[str, str]], handle: str, accent: str, title: str) -> str:
    """Every piece of user text goes through html.escape. The accent colour is
    validated as #rrggbb before it gets near the stylesheet."""
    if not HEX.match(accent):
        raise ValueError("accent must be #rrggbb")
    esc = lambda t: html.escape(t, quote=True)
    n = len(slides)
    pages = []
    for i, s in enumerate(slides, 1):
        body_lines = [ln for ln in s["body"].splitlines() if ln.strip()]
        is_list = sum(1 for ln in body_lines if BULLET.match(ln)) >= 2
        if is_list:
            # no backslashes inside f-string expressions: that is a syntax error before Python 3.12
            items = "".join("<li>" + esc(BULLET.sub("", ln)) + "</li>" for ln in body_lines)
            body = f"<ul>{items}</ul>"
        else:
            body = "".join(f"<p>{esc(ln)}</p>" for ln in body_lines)
        cls = "slide cover" if i == 1 else "slide"
        pages.append(f'<section class="{cls}"><div class="num">{i}/{n}</div>'
                     f'<h1>{esc(s["headline"])}</h1><div class="body">{body}</div>'
                     f'<div class="handle">{esc(handle)}</div></section>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #111111; }}
.slide {{ width: {W}px; height: {H}px; padding: 120px 96px; position: relative; overflow: hidden;
  page-break-after: always; break-after: page; display: flex; flex-direction: column; justify-content: center; }}
.slide:last-child {{ page-break-after: auto; break-after: auto; }}
.cover {{ background: {accent}; color: #ffffff; }}
h1 {{ font-size: 84px; line-height: 1.08; margin: 0 0 48px; letter-spacing: -1px; }}
.cover h1 {{ font-size: 110px; }}
.body p, .body li {{ font-size: 44px; line-height: 1.35; margin: 0 0 24px; }}
.body ul {{ padding-left: 48px; margin: 0; }}
.num {{ position: absolute; top: 56px; right: 72px; font-size: 32px; opacity: .6; }}
.handle {{ position: absolute; bottom: 56px; left: 96px; font-size: 30px; opacity: .7; }}
.slide:not(.cover) h1 {{ color: {accent}; }}
</style></head><body>
{chr(10).join(pages)}
</body></html>
"""


def find_chrome() -> Optional[str]:
    for c in CHROMES:
        p = shutil.which(c) or (c if os.path.isabs(c) and os.path.exists(c) else None)
        if p:
            return p
    return None


def print_pdf(html_path: str, pdf_path: str) -> Tuple[bool, str]:
    chrome = find_chrome()
    if not chrome:
        return False, "no Chrome or Chromium found. Open the HTML in a browser and Print -> Save as PDF."
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={os.path.abspath(pdf_path)}", "file://" + os.path.abspath(html_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)   # list args, no shell
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Chrome did not finish: {e}"
    if r.returncode != 0 or not os.path.exists(pdf_path):
        return False, f"Chrome exited {r.returncode}: {r.stderr.strip()[:200]}"
    return True, pdf_path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Lint carousel copy and build the 1080x1350 document.")
    ap.add_argument("input", help="slides file, --- between slides, or - for stdin")
    ap.add_argument("--handle", default="", help="your name or handle, printed small on every slide")
    ap.add_argument("--accent", default="#0a66c2", help="one accent colour, #rrggbb")
    ap.add_argument("-o", "--out", default="carousel.html")
    ap.add_argument("--pdf", help="also print to this PDF with headless Chrome, if installed")
    ap.add_argument("--lint-only", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as e:
        print(f"could not read input: {e}", file=sys.stderr)
        return 2
    slides = parse(raw)
    if not slides:
        print("no slides found. Separate slides with a line containing only ---", file=sys.stderr)
        return 2
    if not HEX.match(args.accent):
        print("--accent must look like #0a66c2", file=sys.stderr)
        return 2
    print(f"\nCAROUSEL  ·  {len(slides)} slides\n")
    for i, s in enumerate(slides, 1):
        print(f"  {i:>2}. {s['headline']}  ({nwords(s['body'])} words)")
    print("")
    for status, name, msg in lint(slides):
        print(f"  {status:<5} {name:<9} {msg}")
    print("")
    if args.lint_only:
        return 0
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render_html(slides, args.handle, args.accent, slides[0]["headline"]))
    print(f"  wrote {args.out}  ({W}x{H}, one page per slide)")
    if args.pdf:
        ok, msg = print_pdf(args.out, args.pdf)
        print(f"  {'wrote ' + msg if ok else 'PDF skipped: ' + msg}")
    print("  Upload the PDF to LinkedIn yourself, with 2-3 lines of post text above it.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
