# Security policy

## What this pack touches

Everything runs locally on files you give it. The one exception is the opt-in
`/li-publish` tool, which talks only to `linkedin.com` and `api.linkedin.com`
over HTTPS (it refuses any other host). It asks for your developer app's
Client ID and Secret in your own terminal (the secret with hidden input),
never stores the secret, and keeps only the access token, in a file
readable by you alone. The OAuth callback listens on 127.0.0.1 only, checks
a random `state` value in constant time, and echoes nothing back. No other
tool asks for, stores or transmits credentials. Your files under
`~/.claude/linkedin/` stay on your machine.

Hardening already in place: `.xlsx` imports cap decompressed size and never
resolve external entities; the engagement ledger neutralises cells that
would be read as spreadsheet formulas; generated carousel HTML escapes all
user text and validates the accent colour; headless Chrome is called with an
argument list, never a shell; calendar files escape and fold every field.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability
reporting on this repository (Security -> Report a vulnerability). Expect an
acknowledgement within a week.
