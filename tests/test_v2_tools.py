"""Tests for the LinkedIn v2 tools: count.py, audit.py (CSV and .xlsx),
carousel.py and preflight.py."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
for sub in ("li-post", "li-audit", "li-carousel", "li-preflight"):
    sys.path.insert(0, os.path.join(SK, sub))

import audit       # noqa: E402
import carousel    # noqa: E402
import count       # noqa: E402
import preflight   # noqa: E402

POST = ("Writing a proposal used to take me 5 hours. It now takes 20 minutes.\n\n"
        "Here's what changed. I stopped writing proposals from scratch. One template, 6 blocks.\n\n"
        "The pricing table moved out of the doc. That cut a full review round.\n\n"
        "Last quarter we sent 41 proposals. 14 closed. The year before we sent 12.\n\n"
        "What is the one document you still write from scratch every time?\n")


def tmp(text, suffix=".txt"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def run(tool, *args):
    return subprocess.run([sys.executable, os.path.join(SK, tool), *args], capture_output=True, text=True,
                          timeout=60)


def statuses(a):
    return {c["check"]: c["status"] for c in a["checks"]}


class CountTests(unittest.TestCase):
    def test_clean_post(self):
        a = count.analyse(POST)
        s = statuses(a)
        self.assertTrue(a["fits"])
        self.assertEqual(s["FIRST LINE"], "PASS")
        self.assertEqual(s["LINKS"], "PASS")

    def test_limits_per_kind(self):
        self.assertFalse(count.analyse("x" * 3001)["fits"])
        self.assertTrue(count.analyse("x" * 3000)["fits"])
        self.assertFalse(count.analyse("x" * 201, "invite")["fits"])
        self.assertTrue(count.analyse("x" * 201, "invite", limit=300)["fits"])
        self.assertFalse(count.analyse("x" * 221, "headline")["fits"])
        self.assertFalse(count.analyse("x" * 1251, "comment")["fits"])

    def test_emoji_counts_two(self):
        self.assertEqual(count.units("🚀"), 2)

    def test_post_lints(self):
        text = "x" * 160 + "\n\n" + "y" * 400 + "\n\nRead https://example.com #a #b #c #d\n\nThoughts?"
        s = statuses(count.analyse(text))
        for k in ("FIRST LINE", "LINKS", "HASHTAGS", "WALL", "BAIT"):
            self.assertEqual(s[k], "WARN", k)

    def test_fold_respects_lines_and_chars(self):
        self.assertEqual(count.fold("a\nb\nc\nd", "post", 140), "a\nb\nc")
        self.assertEqual(len(count.fold("z" * 500, "post", 140)), 140)

    def test_comment_invite_headline_tells(self):
        self.assertIn("OPENER", statuses(count.analyse("Great post! I agree.", "comment")))
        self.assertIn("ASK", statuses(count.analyse("Would love to book a call", "invite")))
        self.assertIn("TELLS", statuses(count.analyse("Helping founders scale", "headline")))

    def test_cli(self):
        self.assertEqual(run("li-post/count.py", tmp(POST)).returncode, 0)
        self.assertEqual(run("li-post/count.py", tmp("x" * 3001)).returncode, 1)
        self.assertEqual(run("li-post/count.py", tmp("  ")).returncode, 2)
        self.assertEqual(run("li-post/count.py", "--kind", "invite", "--text", "hi", "--limit", "0").returncode, 2)


def make_csv(n=30):
    path = tmp("", ".csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Post commentary", "Post URL", "Post publish date", "Impressions", "Reactions", "Comments",
                    "Reposts"])
        for i in range(n):
            link = i % 3 == 0
            text = f"Post {i} about a cost I paid" + (" https://example.com" if link else "")
            er = 0.01 if link else 0.04
            imp = 1000 + i * 50
            w.writerow([text, f"https://linkedin.com/p/{i}", "09/%02d/2026" % (i % 28 + 1), imp,
                        int(imp * er * 0.8), int(imp * er * 0.15), int(imp * er * 0.05)])
    return path


def make_xlsx():
    strings = ["Post URL", "Post publish date", "Engagements", "Impressions"]
    header = [0, 1, 2, None, 0, 1, 3]
    for i in range(6):
        strings += [f"u{i}", f"09/0{i + 1}/2026"]
    sheet = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
             '<row r="1">' + "".join(f'<c r="{chr(65 + c)}1" t="s"><v>{v}</v></c>'
                                     for c, v in enumerate(header) if v is not None) + "</row>"]
    for i in range(6):
        u, d = 4 + 2 * i, 5 + 2 * i
        u2, d2 = 4 + 2 * (5 - i), 5 + 2 * (5 - i)
        vals = [u, d, 10 * (i + 1), None, u2, d2, 1000]
        sheet.append(f'<row r="{i + 2}">' + "".join(
            (f'<c r="{chr(65 + c)}{i + 2}" t="s"><v>{v}</v></c>' if c in (0, 1, 4, 5) else
             f'<c r="{chr(65 + c)}{i + 2}"><v>{v}</v></c>') for c, v in enumerate(vals) if v is not None) + "</row>")
    sheet.append("</sheetData></worksheet>")
    sst = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
    path = tmp("", ".xlsx")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   '<sheet name="TOP POSTS" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                   '</Relationships>')
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", "".join(sheet))
    return path


class AuditTests(unittest.TestCase):
    def test_csv_finds_the_link_effect(self):
        posts, src = audit.load(make_csv())
        a = audit.analyse(posts, 3000, None)
        self.assertEqual(len(a["posts"]), 30)
        dims = {(f["dimension"], f["group"]) for f in a["findings"]}
        self.assertTrue(("link", "no link") in dims or ("link", "link in body") in dims, dims)
        self.assertIsNotNone(a["posts"][0]["reach_multiple"])

    def test_xlsx_side_by_side_tables_merge_on_url(self):
        posts, src = audit.load(make_xlsx())
        self.assertEqual(src, "TOP POSTS")
        self.assertEqual(len(posts), 6)
        by = {p["link"]: p for p in posts}
        self.assertEqual(by["u5"]["engagements"], 60)
        self.assertEqual(by["u5"]["impressions"], 1000)

    def test_excel_serial_dates(self):
        self.assertEqual(audit.parse_date("46000").year, 2025)

    def test_bad_files(self):
        self.assertEqual(run("li-audit/audit.py", tmp("a,b\n1,2\n", ".csv")).returncode, 2)
        self.assertEqual(run("li-audit/audit.py", tmp("not a zip", ".xlsx")).returncode, 2)
        self.assertEqual(run("li-audit/audit.py", make_csv(), "--followers", "0").returncode, 2)
        self.assertEqual(run("li-audit/audit.py", make_csv(), "--json").returncode, 0)


SLIDES = "\n---\n".join(
    ["# Proposals in 20 minutes\nThe template we use"]
    + [f"Step {i} does one thing\nOne short line of body for step {i}." for i in range(1, 8)]
    + ["The whole thing at once\n- one\n- two\n- three", "Follow for the next one\nComment TEMPLATE"])


class CarouselTests(unittest.TestCase):
    def test_parse_and_lint_clean_deck(self):
        slides = carousel.parse(SLIDES)
        self.assertEqual(len(slides), 10)
        self.assertEqual(slides[0]["headline"], "Proposals in 20 minutes")
        self.assertEqual([x for x in carousel.lint(slides) if x[0] == "WARN"], [])

    def test_lint_catches_problems(self):
        bad = carousel.parse("A very long cover headline with far too many words\n---\nHi\n" + "word " * 30)
        names = [x[1] for x in carousel.lint(bad)]
        self.assertIn("SLIDES", names)
        self.assertIn("COVER", names)
        self.assertIn("SLIDE 2", names)

    def test_html_escapes_everything(self):
        html = carousel.render_html(carousel.parse("<script>x</script>\n<img src=y>"), '"><b>', "#0a66c2", "<t>")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn('"><b>', html)
        self.assertIn("1080px", html)

    def test_accent_is_validated(self):
        with self.assertRaises(ValueError):
            carousel.render_html(carousel.parse("a\nb"), "", "red;}body{display:none", "t")
        self.assertEqual(run("li-carousel/carousel.py", tmp(SLIDES), "--accent", "blue").returncode, 2)

    def test_cli_writes_html(self):
        out = tmp("", ".html")
        r = run("li-carousel/carousel.py", tmp(SLIDES), "--handle", "Sarah Chen", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(fh.read().count('class="slide'), 10)


class PreflightTests(unittest.TestCase):
    def test_ready_and_blocked(self):
        self.assertTrue(preflight.run(POST)["ready"])
        r = preflight.run("x" * 3001)
        self.assertFalse(r["ready"])

    def test_kinds(self):
        r = preflight.run("Saw your post on pricing. I run ops at a 12-person studio.", kind="invite")
        self.assertEqual(r["kind"], "invite")
        self.assertEqual(r["stages"][0]["status"], "PASS")

    def test_cli(self):
        tool = os.path.join(SK, "li-preflight", "preflight.py")
        ok = subprocess.run([sys.executable, tool, tmp(POST), "--json"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["ready"])


if __name__ == "__main__":
    unittest.main()
