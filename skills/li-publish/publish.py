#!/usr/bin/env python3
"""
publish.py - publish an approved post to your own LinkedIn profile through
LinkedIn's official API. Opt-in, one post at a time, never without a preview.

Everything else in this pack writes and you paste. This is the one tool that
sends, so it is built around one rule: what gets published is exactly the
text you approved, and nothing else.

  1. `preview` runs /li-preflight on the draft, shows the exact text, and
     prints a confirmation code derived from that text.
  2. `post --confirm CODE` publishes only if the file still hashes to that
     code, pre-flight still says READY, it is not a duplicate, and you are
     under the daily cap. Change one character and the code no longer
     matches, so an edited draft has to be previewed again.

It uses the official route, LinkedIn's Posts API with the w_member_social
permission from the "Share on LinkedIn" product, through a developer app you
create and own. It does not drive a browser, does not scrape, and does not
comment, react, connect or message: automating those is what gets accounts
restricted, so they stay manual.

One-time setup (see SKILL.md for the developer-app steps):
  python3 publish.py auth             # opens LinkedIn's own sign-in page in your browser
  python3 publish.py status           # who is connected, and for how long

Every post:
  python3 publish.py preview draft.txt
  python3 publish.py post draft.txt --confirm 3f9a1c0be2

Other:
  python3 publish.py history          # what this tool has published
  python3 publish.py logout           # delete the stored token

Your token lives in ~/.claude/linkedin/credentials.json, readable only by
you, and is never printed. Standard library only.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "li-preflight"))

HOME = os.path.expanduser(os.environ.get("LI_AGENT_HOME", "~/.claude/linkedin"))
CREDS = os.path.join(HOME, "credentials.json")
LOG = os.path.join(HOME, "published.jsonl")

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
SCOPES = "openid profile w_member_social"
API_VERSION = os.environ.get("LINKEDIN_API_VERSION", "202610")   # YYYYMM; each is supported for 1+ year
DEFAULT_PORT = 8765
DAILY_CAP = 2
MAX_CAP = 5
CODE_LEN = 10
POST_LIMIT = 3000

# little text: every one of these must be backslash-escaped in `commentary`,
# or LinkedIn truncates the post or rejects it.
RESERVED = set("|{}@[]()<>#\\*_~")
HASHTAG_RE = re.compile(r"(?:(?<=\s)|^)#([A-Za-z][A-Za-z0-9_]{0,99})\b")

Http = Callable[[str, str, Dict[str, str], Optional[bytes]], Tuple[int, Dict[str, str], bytes]]


class PublishError(Exception):
    pass


# ------------------------------------------------------------------ text

def escape_little_text(text: str) -> str:
    """Escape LinkedIn's reserved characters, turning real hashtags into the
    hashtag template so they still link."""
    out: List[str] = []
    pos = 0
    for m in HASHTAG_RE.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        out.append("{hashtag|\\#|" + _escape(m.group(1)) + "}")
        pos = m.end()
    out.append(_escape(text[pos:]))
    return "".join(out)


def _escape(s: str) -> str:
    return "".join("\\" + c if c in RESERVED else c for c in s)


def normalise(raw: str) -> str:
    return raw.replace("\r\n", "\n").strip()


def confirm_code(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:CODE_LEN]


# ------------------------------------------------------------------ files

def _private_write(path: str, data: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_creds(path: str = CREDS) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
    except FileNotFoundError:
        raise PublishError("not connected. Run `publish.py auth` once first.")
    except ValueError:
        raise PublishError(f"{path} is corrupt. Run `publish.py logout`, then `publish.py auth`.")
    for k in ("access_token", "expires_at", "sub"):
        if not c.get(k):
            raise PublishError(f"{path} is missing {k}. Run `publish.py auth` again.")
    if c["expires_at"] <= time.time() + 60:
        raise PublishError("your LinkedIn token has expired. Run `publish.py auth` again (it takes a minute).")
    return c


def read_log(path: str = LOG) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def append_log(row: Dict[str, Any], path: str = LOG) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def posted_today(rows: List[Dict[str, Any]], now: Optional[float] = None) -> int:
    now = now or time.time()
    return sum(1 for r in rows if now - float(r.get("ts", 0)) < 24 * 3600)


# ------------------------------------------------------------------ http

def real_http(method: str, url: str, headers: Dict[str, str], body: Optional[bytes]) -> Tuple[int, Dict[str, str], bytes]:
    if not url.startswith(("https://www.linkedin.com/", "https://api.linkedin.com/")):
        raise PublishError("refusing to send a request anywhere but linkedin.com")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read() or b""
    except urllib.error.URLError as e:
        raise PublishError(f"could not reach LinkedIn: {e.reason}")


def api_error(status: int, body: bytes) -> str:
    try:
        d = json.loads(body.decode("utf-8", "replace"))
        msg = d.get("message") or d.get("error_description") or d.get("error") or ""
        code = d.get("code") or d.get("serviceErrorCode") or ""
    except ValueError:
        msg, code = body.decode("utf-8", "replace")[:200], ""
    hint = {
        401: "The token was rejected. Run `publish.py auth` again.",
        403: "The app is missing permission. Check that the app has the \"Share on LinkedIn\" product and you "
             "approved w_member_social when signing in.",
        422: "LinkedIn rejected the post content. Usually an unescaped character or an over-long post.",
        426: f"LinkedIn-Version {API_VERSION} is no longer active. Set LINKEDIN_API_VERSION to a recent YYYYMM "
             "(see LinkedIn's versioning page) and try again.",
        429: "Rate limited by LinkedIn. Wait and try again tomorrow.",
    }.get(status, "")
    return f"LinkedIn returned {status} {code}: {msg}".strip() + (f"\n  {hint}" if hint else "")


# ------------------------------------------------------------------ auth

def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    q = urllib.parse.urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
                                "state": state, "scope": SCOPES})
    return f"{AUTH_URL}?{q}"


def check_callback(path: str, expected_state: str) -> str:
    """Validate the redirect LinkedIn sent back and return the auth code.
    The state check is constant-time, and nothing from the query is echoed."""
    u = urllib.parse.urlparse(path)
    if u.path != "/callback":
        raise PublishError("unexpected path")
    q = urllib.parse.parse_qs(u.query)
    if "error" in q:
        raise PublishError(f"LinkedIn sign-in was not completed: {q.get('error', [''])[0][:60]}")
    state = q.get("state", [""])[0]
    code = q.get("code", [""])[0]
    if not state or not hmac.compare_digest(state, expected_state):
        raise PublishError("state mismatch: this redirect did not come from the sign-in this tool started")
    if not code:
        raise PublishError("no authorisation code in the redirect")
    return code


def wait_for_code(port: int, expected_state: str, timeout: int = 300) -> str:
    result: Dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if urllib.parse.urlparse(self.path).path != "/callback":
                self.send_response(404)                            # e.g. the browser's /favicon.ico
                self.end_headers()
                return
            try:
                result["code"] = check_callback(self.path, expected_state)
                msg, status = "Connected. You can close this tab and go back to Claude.", 200
            except PublishError as e:
                result.setdefault("error", str(e))
                msg, status = "Sign-in did not complete. Go back to the terminal for details.", 400
            body = f"<!doctype html><meta charset=utf-8><title>LinkedIn agent</title><p>{html.escape(msg)}</p>"
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, *_):
            pass                                                   # never log the code to the terminal

    server = HTTPServer(("127.0.0.1", port), Handler)            # loopback only
    server.timeout = 5
    deadline = time.time() + timeout
    try:
        while time.time() < deadline and "code" not in result:
            server.handle_request()
            if "error" in result and "code" not in result:
                raise PublishError(result["error"])
    finally:
        server.server_close()
    if "code" not in result:
        raise PublishError("timed out waiting for LinkedIn sign-in (5 minutes)")
    return result["code"]


def exchange_and_save(code: str, client_id: str, client_secret: str, redirect_uri: str,
                      http: Http = real_http, path: str = CREDS) -> Dict[str, Any]:
    body = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                                   "client_id": client_id, "client_secret": client_secret}).encode()
    status, _, raw = http("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if status != 200:
        raise PublishError(api_error(status, raw))
    tok = json.loads(raw)
    token = tok.get("access_token")
    if not token:
        raise PublishError("LinkedIn did not return an access token")
    granted = set((tok.get("scope") or SCOPES).replace(",", " ").split())
    if "w_member_social" not in granted:
        raise PublishError("the token does not include w_member_social. Add the \"Share on LinkedIn\" product to "
                           "your app and sign in again.")
    status, _, raw = http("GET", USERINFO_URL, {"Authorization": f"Bearer {token}"}, None)
    if status != 200:
        raise PublishError(api_error(status, raw))
    me = json.loads(raw)
    if not me.get("sub"):
        raise PublishError("LinkedIn did not return your member id (sub)")
    creds = {"access_token": token, "expires_at": int(time.time()) + int(tok.get("expires_in", 0)),
             "sub": me["sub"], "name": me.get("name", ""), "scope": " ".join(sorted(granted)),
             "connected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _private_write(path, json.dumps(creds, indent=2))
    return creds


def cmd_auth(args: argparse.Namespace) -> int:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID") or input("LinkedIn app Client ID: ").strip()
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or getpass.getpass("LinkedIn app Client Secret (hidden): ").strip()
    if not client_id or not client_secret:
        print("need both the Client ID and the Client Secret from your app's Auth tab", file=sys.stderr)
        return 2
    redirect = args.redirect_uri or f"http://localhost:{args.port}/callback"
    state = secrets.token_urlsafe(24)
    url = auth_url(client_id, redirect, state)
    print(f"\nOpening LinkedIn's sign-in page. If it does not open, paste this into your browser:\n\n  {url}\n")
    print(f"Waiting for the redirect to {redirect} ...")
    webbrowser.open(url)
    try:
        code = wait_for_code(args.port, state)
        creds = exchange_and_save(code, client_id, client_secret, redirect)
    except (PublishError, OSError, ValueError) as e:
        print(f"\nnot connected: {e}", file=sys.stderr)
        return 1
    days = (creds["expires_at"] - time.time()) / 86400
    print(f"\nConnected as {creds['name'] or creds['sub']}. Token valid for about {days:.0f} days. "
          f"Stored in {CREDS} (owner-only).\n")
    return 0


# ------------------------------------------------------------------ posting

def payload(text: str, author_sub: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    return {
        "author": f"urn:li:person:{author_sub}",
        "commentary": escape_little_text(normalise(text)),
        "visibility": visibility,
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def gate(text: str, rows: List[Dict[str, Any]], cap: int, run_preflight: bool = True) -> Dict[str, Any]:
    """Everything that must be true before a post can go. Returns the
    pre-flight result; raises PublishError with the reason otherwise."""
    t = normalise(text)
    if not t:
        raise PublishError("the draft is empty")
    if len(t.encode("utf-16-le")) // 2 > POST_LIMIT:
        raise PublishError(f"over LinkedIn's {POST_LIMIT:,}-character limit")
    if "{{" in t and "}}" in t:
        raise PublishError("the draft still has a {{placeholder}} in it. Fill it with the real fact, or cut the line.")
    code = confirm_code(t)
    if any(r.get("hash") == code for r in rows):
        raise PublishError("this exact text was already published by this tool")
    if posted_today(rows) >= cap:
        raise PublishError(f"daily cap reached ({cap} in the last 24 hours). Posting more often rarely helps reach; "
                           "schedule it in LinkedIn instead.")
    pf: Dict[str, Any] = {"ready": True, "stages": [], "fixes": []}
    if run_preflight:
        import preflight                                        # noqa: E402  (sibling skill)
        pf = preflight.run(t, "post")
        if not pf["ready"]:
            raise PublishError("pre-flight says FIX FIRST:\n  " + "\n  ".join(pf["fixes"][:5]))
    return pf


def publish(text: str, creds: Dict[str, Any], visibility: str = "PUBLIC", http: Http = real_http) -> str:
    body = json.dumps(payload(text, creds["sub"], visibility)).encode("utf-8")
    headers = {"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json",
               "LinkedIn-Version": API_VERSION, "X-Restli-Protocol-Version": "2.0.0"}
    status, hdrs, raw = http("POST", POSTS_URL, headers, body)
    if status != 201:
        raise PublishError(api_error(status, raw))
    return hdrs.get("x-restli-id", "")


def read_draft(path: str) -> str:
    try:
        if path == "-":
            return sys.stdin.read()
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as e:
        raise PublishError(f"could not read {path}: {e}")


def cmd_preview(args: argparse.Namespace) -> int:
    try:
        text = normalise(read_draft(args.draft))
        pf = gate(text, read_log(), args.cap)
    except PublishError as e:
        print(f"\nNOT READY TO PUBLISH\n  {e}\n", file=sys.stderr)
        return 1
    print("\nTHIS EXACT TEXT WOULD BE PUBLISHED" + (" (connections only)" if args.connections else " (public)"))
    print("-" * 66)
    print(text)
    print("-" * 66)
    for s in pf["stages"]:
        print(f"  {s['stage']:<6} {s['status']:<5} {s['detail']}")
    for f in pf["fixes"]:
        print(f"  note: {f}")
    print(f"\n  confirmation code: {confirm_code(text)}")
    print(f"  publish with:      python3 publish.py post {args.draft} --confirm {confirm_code(text)}"
          + (" --connections" if args.connections else ""))
    print("  Any edit to the draft changes the code, so an edited draft needs a fresh preview.\n")
    return 0


def cmd_post(args: argparse.Namespace) -> int:
    try:
        text = normalise(read_draft(args.draft))
        if not hmac.compare_digest(args.confirm.strip().lower(), confirm_code(text)):
            raise PublishError("the confirmation code does not match this text. The draft changed since it was "
                               "previewed, or the code is from a different draft. Run `preview` again.")
        rows = read_log()
        gate(text, rows, args.cap)
        creds = load_creds()
        urn = publish(text, creds, "CONNECTIONS" if args.connections else "PUBLIC")
    except PublishError as e:
        print(f"\nNOT PUBLISHED\n  {e}\n", file=sys.stderr)
        return 1
    first = next((ln for ln in text.splitlines() if ln.strip()), "")[:100]
    append_log({"ts": time.time(), "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "hash": confirm_code(text), "urn": urn, "first_line": first,
                "visibility": "CONNECTIONS" if args.connections else "PUBLIC"})
    url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else "(LinkedIn did not return the post id)"
    print(f"\nPUBLISHED  {url}\n  Be there for the first hour of comments: /li-reply drafts the answers.\n")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    try:
        c = load_creds()
    except PublishError as e:
        print(str(e))
        return 1
    days = (c["expires_at"] - time.time()) / 86400
    rows = read_log()
    print(f"\n  connected as   {c.get('name') or c['sub']}")
    print(f"  token expires  in {days:.0f} days" + ("  <- re-run auth soon" if days < 7 else ""))
    print(f"  scopes         {c.get('scope', '')}")
    print(f"  published      {len(rows)} total, {posted_today(rows)} in the last 24 hours\n")
    return 0


def cmd_history(_: argparse.Namespace) -> int:
    rows = read_log()
    if not rows:
        print("nothing published by this tool yet")
        return 0
    for r in rows[-20:]:
        print(f"  {r.get('date', '')[:16]}  {r.get('visibility', ''):<11}  {r.get('first_line', '')[:60]}")
    return 0


def cmd_logout(_: argparse.Namespace) -> int:
    if os.path.exists(CREDS):
        os.remove(CREDS)
        print("token deleted. To revoke the app's access entirely: LinkedIn -> Settings -> Data privacy -> "
              "Permitted services.")
    else:
        print("not connected")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Publish an approved post to your LinkedIn profile via the official API.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auth", help="connect your LinkedIn developer app (one time, ~60 days)")
    a.add_argument("--port", type=int, default=DEFAULT_PORT)
    a.add_argument("--redirect-uri", help=f"must match the app's Authorized redirect URL (default http://localhost:{DEFAULT_PORT}/callback)")
    for name in ("preview", "post"):
        p = sub.add_parser(name)
        p.add_argument("draft", help="the post text file, or - for stdin")
        p.add_argument("--connections", action="store_true", help="visible to connections only (default public)")
        p.add_argument("--cap", type=int, default=DAILY_CAP, help=f"max posts per 24 hours (default {DAILY_CAP}, max {MAX_CAP})")
        if name == "post":
            p.add_argument("--confirm", required=True, help="the code `preview` printed for this exact text")
    sub.add_parser("status")
    sub.add_parser("history")
    sub.add_parser("logout")
    args = ap.parse_args(argv)
    if getattr(args, "cap", 1) is not None and not 1 <= getattr(args, "cap", 1) <= MAX_CAP:
        print(f"--cap must be between 1 and {MAX_CAP}", file=sys.stderr)
        return 2
    if args.cmd == "auth" and not 1024 <= args.port <= 65535:
        print("--port must be between 1024 and 65535", file=sys.stderr)
        return 2
    return {"auth": cmd_auth, "preview": cmd_preview, "post": cmd_post, "status": cmd_status,
            "history": cmd_history, "logout": cmd_logout}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
