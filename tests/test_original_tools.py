"""Regression tests for the two tools that shipped in v1: humanize.py and detect.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")


def run(tool, *args):
    return subprocess.run([sys.executable, os.path.join(SK, tool), *args], capture_output=True, text=True,
                          timeout=60)


def tmp(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


BAD = ("In today’s fast-paced world, it is crucial to leverage robust synergies — moreover, we must "
       "delve into the tapestry of growth.​ Let that sink in. It’s not just a strategy, it’s a "
       "mindset. Thoughts?\n")
GOOD = ("I raised prices 40% in March and lost 2 of 31 clients. The two we lost were the two we argued with "
        "most. I'd do it again. Next time I'd do it in January, before the renewals, not after.\n")


class HumanizeTests(unittest.TestCase):
    def test_cleans_and_preserves_urls(self):
        src = tmp(BAD + "See https://example.com/delve-robust for more.\n")
        out = src + ".out"
        r = run("li-human/humanize.py", src, "-o", out, "--report")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        for bad in ("—", "​", "’", "delve into", "leverage"):
            self.assertNotIn(bad, text)
        self.assertIn("https://example.com/delve-robust", text)

    def test_lexicon_is_valid(self):
        with open(os.path.join(SK, "li-human", "slop.json"), encoding="utf-8") as fh:
            lex = json.load(fh)
        # README: 113 terms (81 words + 32 phrases), 17 invisible classes, 11 structural tells
        self.assertEqual(len(lex["words"]) + len(lex["phrases"]), 113)
        self.assertEqual(len(lex["invisible"]), 17)
        self.assertEqual(len(lex["structures"]), 11)


class DetectTests(unittest.TestCase):
    def test_bad_flagged_good_better(self):
        r = run("li-human/detect.py", tmp(BAD), tmp(GOOD), "--json")
        payload = json.loads(r.stdout)
        self.assertLess(payload[0]["human_score"], payload[-1]["human_score"])
        self.assertNotEqual(payload[0]["verdict"], "PASS")

    def test_exit_code_tracks_verdict(self):
        self.assertEqual(run("li-human/detect.py", tmp(BAD)).returncode, 1)


class HooksAndRubricTests(unittest.TestCase):
    def test_hooks_json(self):
        with open(os.path.join(SK, "li-post", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        self.assertEqual(len(hooks), 21)

    def test_rubric_totals_100(self):
        with open(os.path.join(SK, "li-profile", "rubric.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        self.assertEqual(sum(i["points"] for i in r["items"]), 100)


if __name__ == "__main__":
    unittest.main()
