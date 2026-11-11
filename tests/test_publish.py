"""Tests for li-publish. No network: LinkedIn is replaced by a fake HTTP
function, and the home directory by a temp folder."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest

TMP_HOME = tempfile.mkdtemp()
os.environ["LI_AGENT_HOME"] = TMP_HOME
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
sys.path.insert(0, os.path.join(SK, "li-publish"))

import publish     # noqa: E402

POST = ("Writing a proposal used to take me 5 hours. It now takes 20 minutes.\n\n"
        "Here's what changed. I stopped writing proposals from scratch. One template, 6 blocks.\n\n"
        "The pricing table moved out of the doc. That cut a full review round.\n\n"
        "Last quarter we sent 41 proposals. 14 closed. The year before we sent 12.\n\n"
        "What is the one document you still write from scratch every time? #operations\n")


class FakeLinkedIn:
    def __init__(self, post_status=201, scope="openid profile w_member_social"):
        self.calls = []
        self.post_status = post_status
        self.scope = scope

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        if url == publish.TOKEN_URL:
            return 200, {}, json.dumps({"access_token": "SECRET-TOKEN", "expires_in": 5184000,
                                        "scope": self.scope}).encode()
        if url == publish.USERINFO_URL:
            return 200, {}, json.dumps({"sub": "782bbtaQ", "name": "Test Person"}).encode()
        if url == publish.POSTS_URL:
            if self.post_status == 201:
                return 201, {"x-restli-id": "urn:li:share:123"}, b""
            return self.post_status, {}, json.dumps({"message": "nope", "code": "X"}).encode()
        raise AssertionError(url)


def reset():
    for f in os.listdir(TMP_HOME):
        os.remove(os.path.join(TMP_HOME, f))


class EscapeTests(unittest.TestCase):
    def test_every_reserved_char_is_escaped(self):
        out = publish.escape_little_text("a|b{c}d@e[f]g(h)i<j>k\\l*m_n~o")
        self.assertEqual(out, "a\\|b\\{c\\}d\\@e\\[f\\]g\\(h\\)i\\<j\\>k\\\\l\\*m\\_n\\~o")

    def test_hashtags_become_templates(self):
        self.assertEqual(publish.escape_little_text("Ship it #ops_team now"),
                         "Ship it {hashtag|\\#|ops\\_team} now")
        self.assertEqual(publish.escape_little_text("#first\n#second"),
                         "{hashtag|\\#|first}\n{hashtag|\\#|second}")

    def test_non_hashtag_hash_is_escaped(self):
        self.assertEqual(publish.escape_little_text("C# and #1"), "C\\# and \\#1")

    def test_plain_text_unchanged(self):
        self.assertEqual(publish.escape_little_text("Plain text, 40% off."), "Plain text, 40% off.")


class GateTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_code_is_stable_and_text_bound(self):
        self.assertEqual(publish.confirm_code(POST), publish.confirm_code(POST.replace("\n", "\r\n") + "  "))
        self.assertNotEqual(publish.confirm_code(POST), publish.confirm_code(POST + "!"))

    def test_rejects_placeholder_empty_long_duplicate_and_cap(self):
        for bad in ("   ", "We grew {{your number}} percent.", "x" * 3001):
            with self.assertRaises(publish.PublishError):
                publish.gate(bad, [], 2, run_preflight=False)
        with self.assertRaises(publish.PublishError):
            publish.gate(POST, [{"hash": publish.confirm_code(POST), "ts": 0}], 2, run_preflight=False)
        now = time.time()
        with self.assertRaises(publish.PublishError):
            publish.gate(POST, [{"hash": "a", "ts": now}, {"hash": "b", "ts": now}], 2, run_preflight=False)
        publish.gate(POST, [{"hash": "a", "ts": now - 90000}], 2, run_preflight=False)

    def test_preflight_runs(self):
        self.assertTrue(publish.gate(POST, [], 2)["ready"])
        slop = ("In today's fast-paced world, it is crucial to leverage robust synergies — moreover, we "
                "must delve into the tapestry of growth. Let that sink in. It's not just a strategy, it's a "
                "mindset. Furthermore, this paradigm is a testament to seamless innovation. Thoughts?")
        with self.assertRaises(publish.PublishError) as cm:
            publish.gate(slop, [], 2)
        self.assertIn("pre-flight", str(cm.exception))


class AuthTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_callback_validation(self):
        self.assertEqual(publish.check_callback("/callback?code=abc&state=s1", "s1"), "abc")
        for path in ("/callback?code=abc&state=WRONG", "/callback?code=abc", "/callback?state=s1",
                     "/callback?error=user_cancelled&state=s1", "/other?code=abc&state=s1"):
            with self.assertRaises(publish.PublishError, msg=path):
                publish.check_callback(path, "s1")

    def test_auth_url(self):
        u = publish.auth_url("cid", "http://localhost:8765/callback", "st")
        self.assertTrue(u.startswith(publish.AUTH_URL))
        self.assertIn("w_member_social", u.replace("+", " ").replace("%20", " "))

    def test_exchange_saves_private_file_without_secret(self):
        fake = FakeLinkedIn()
        path = os.path.join(TMP_HOME, "credentials.json")
        creds = publish.exchange_and_save("code", "cid", "CLIENT-SECRET", "http://localhost:8765/callback",
                                          http=fake, path=path)
        self.assertEqual(creds["sub"], "782bbtaQ")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertNotIn("CLIENT-SECRET", raw)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(publish.load_creds(path)["sub"], "782bbtaQ")

    def test_missing_scope_is_refused(self):
        with self.assertRaises(publish.PublishError):
            publish.exchange_and_save("c", "id", "s", "r", http=FakeLinkedIn(scope="openid profile"),
                                      path=os.path.join(TMP_HOME, "c.json"))

    def test_expired_and_missing_creds(self):
        path = os.path.join(TMP_HOME, "credentials.json")
        with self.assertRaises(publish.PublishError):
            publish.load_creds(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"access_token": "t", "sub": "s", "expires_at": time.time() - 10}, fh)
        with self.assertRaises(publish.PublishError):
            publish.load_creds(path)

    def test_refuses_non_linkedin_hosts(self):
        with self.assertRaises(publish.PublishError):
            publish.real_http("GET", "https://evil.example/", {}, None)


class PublishTests(unittest.TestCase):
    def test_payload_and_headers(self):
        fake = FakeLinkedIn()
        urn = publish.publish(POST, {"access_token": "SECRET-TOKEN", "sub": "782bbtaQ"}, http=fake)
        self.assertEqual(urn, "urn:li:share:123")
        method, url, headers, body = fake.calls[-1]
        d = json.loads(body)
        self.assertEqual(d["author"], "urn:li:person:782bbtaQ")
        self.assertEqual(d["visibility"], "PUBLIC")
        self.assertEqual(d["lifecycleState"], "PUBLISHED")
        self.assertIn("{hashtag|\\#|operations}", d["commentary"])
        self.assertEqual(headers["X-Restli-Protocol-Version"], "2.0.0")
        self.assertRegex(headers["LinkedIn-Version"], r"^\d{6}$")

    def test_errors_carry_hints_not_tokens(self):
        for status in (401, 403, 422, 426, 429):
            with self.assertRaises(publish.PublishError) as cm:
                publish.publish(POST, {"access_token": "SECRET-TOKEN", "sub": "x"}, http=FakeLinkedIn(status))
            self.assertIn(str(status), str(cm.exception))
            self.assertNotIn("SECRET-TOKEN", str(cm.exception))


class CliTests(unittest.TestCase):
    def setUp(self):
        reset()
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(POST)
        f.close()
        self.draft = f.name

    def run_cli(self, *args):
        env = dict(os.environ, LI_AGENT_HOME=TMP_HOME)
        return subprocess.run([sys.executable, os.path.join(SK, "li-publish", "publish.py"), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_preview_prints_code(self):
        r = self.run_cli("preview", self.draft)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(publish.confirm_code(POST), r.stdout)

    def test_post_refuses_wrong_code_before_any_network(self):
        r = self.run_cli("post", self.draft, "--confirm", "0000000000")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not match", r.stderr)

    def test_post_with_right_code_but_no_auth_is_refused(self):
        r = self.run_cli("post", self.draft, "--confirm", publish.confirm_code(POST))
        self.assertEqual(r.returncode, 1)
        self.assertIn("not connected", r.stderr)

    def test_bad_cap(self):
        self.assertEqual(self.run_cli("preview", self.draft, "--cap", "50").returncode, 2)

    def test_status_when_not_connected(self):
        self.assertEqual(self.run_cli("status").returncode, 1)


if __name__ == "__main__":
    unittest.main()
