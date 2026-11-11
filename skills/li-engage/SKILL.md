---
name: li-engage
description: >-
  Keep the user's LinkedIn engagement round honest - log who they commented
  on, catch drift onto the same three people, track the reach / peer / buyer
  mix from the weekly plan, and surface the people on their list they have gone
  quiet on. Use when the user says "who should I engage with today", "who
  have I been commenting on", "log this comment", "am I neglecting anyone",
  or runs their daily engagement round.
---

# li-engage

`/li-plan` builds a list of ten people: 5 reach, 3 peers, 2 buyers. Two weeks
later the user is commenting on the same three people every morning and the
buyers have not heard from them since day four. Neither problem is visible
from inside the feed. This keeps the record that makes both visible.

One tool lives in this folder and it runs:

```bash
python3 targets.py add "Sarah Chen" --tier reach --note "added the churn number"
python3 targets.py report                     # the last 7 days
python3 targets.py due --roster roster.txt    # who on the list has gone quiet
```

The ledger is a CSV at `~/.claude/linkedin/engage.csv`. It never opens
LinkedIn and never posts.

## The roster

Write the ten from `/li-plan` into `~/.claude/linkedin/roster.txt`, one per
line, `name,tier`:

```
Sarah Chen,reach
Marcus Webb,peer
Dana Ruiz,buyer
```

## The daily round

1. `targets.py due --roster ~/.claude/linkedin/roster.txt`. Start at the top:
   the most overdue first.
2. The user pastes those people's latest posts. Draft each comment with
   `/li-comment`.
3. After the user posts a comment by hand, log it with `targets.py add`. One
   line, ten seconds.

## The weekly read

`targets.py report --days 7` prints the count per person, the share the top
three took, and the tier mix against the 50 / 30 / 20 target. It warns when:

- **three people took over half** of the round. It is visible, to them and to
  everyone reading the comments.
- **a tier fell below half its target.** Usually buyers, because commenting
  on buyers feels like selling. It is not, if the comment is good.

Hand the report to `/li-plan` so next week's list replaces the people who
never engage back.

## Never

- Never comment, react or connect on the user's behalf, and never use a
  browser tool to do it. Automated engagement violates LinkedIn's User
  Agreement and gets accounts restricted.
- Never log an interaction the user did not make.
