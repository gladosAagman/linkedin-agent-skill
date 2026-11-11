---
name: li-preflight
description: >-
  Run every check in the pack on one LinkedIn draft - length and the
  "see more" fold, links, hashtags, bait, walls of text, the five-check
  humanizer panel, and drift from the user's measured voice - and return one
  READY or FIX FIRST verdict with the fixes in order. Use before any post,
  comment, invite note, headline or about section goes out, or when the user
  says "check this", "is this ready", "preflight", or "can I post this".
---

# li-preflight

The pack has a counter, a humanizer panel and a voice check, and the one
that gets skipped is the one that would have caught it. This runs all three
on the same text and gives one answer.

```bash
python3 preflight.py draft.txt                       # a post
python3 preflight.py comment.txt --kind comment
python3 preflight.py note.txt --kind invite
python3 preflight.py headline.txt --kind headline
```

| stage | tool | fails when |
| --- | --- | --- |
| COUNT | `../li-post/count.py` | over the limit for that surface |
| HUMAN | `../li-human/detect.py` | the five-check panel says FLAGGED |
| VOICE | `../li-voice/voice.py` | the draft drifted from the user's measured voice (only when `~/.claude/linkedin/voice.json` exists) |

Warnings do not block. They are listed under the verdict in the order to fix
them.

## Order of operations

1. Draft with the right skill (`/li-post`, `/li-comment`, `/li-dm`,
   `/li-profile`).
2. `humanize.py` from `/li-human`, then rewrite the flagged lines by hand.
3. `preflight.py` on the result.
4. FIX FIRST: fix item 1, run it again. READY: show the user the text, then
   the pre-flight table. Never the table alone.

## What READY does not mean

It means nothing mechanical is wrong. It does not mean the post is good,
and it is not a prediction of reach. A READY post with nothing true in it is
still a post with nothing true in it.

Nothing is posted by this skill. The user pastes the text into LinkedIn.
