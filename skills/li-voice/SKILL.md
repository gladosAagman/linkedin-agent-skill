---
name: li-voice
description: >-
  Measure the user's actual LinkedIn voice from their own past posts and write
  voice.md from evidence, then check any draft for drift before it goes out.
  Use when the user says "write my voice.md", "learn how I write", "does this
  sound like me", "this doesn't sound like me", sets up the pack for the first
  time, or pastes several of their own posts.
---

# li-voice

Every skill in this pack reads `~/.claude/linkedin/voice.md`. Filled in by
hand, it says how the user would like to sound. Measured from their posts, it
says how they do sound, and that is the version their network recognises.
LinkedIn now holds back posts that read as low-effort AI. The fix is not a
detector trick. It is sounding like the person whose name is on the post.

One tool lives in this folder and it runs:

```bash
python3 voice.py samples.txt                                   # measure, print the profile
python3 voice.py samples.txt --save ~/.claude/linkedin/voice.json
python3 voice.py --profile ~/.claude/linkedin/voice.json --check draft.txt
```

## Input

Five to fifteen of the user's own posts, pasted into one file with a line of
`---` between them. Their own posts, written before they used AI on them if
possible. Ghostwritten posts measure the ghostwriter.

Fewer than five and the tool says so. Do not pad the sample with posts you
wrote for them.

## What it measures

Sentence length and how much it varies, contractions, I / we / you, how often
they ask questions or exclaim, casing, emoji, em dashes, how many numbers they
use, and the words and openers that recur across posts. Each one is a mean
and a spread, so a draft is judged against the user's own range, not against
a rule.

## Then write voice.md

1. Run `voice.py` on the samples and save the JSON profile.
2. Fill in `templates/voice.md` from what the user tells you (who they write
   for, what they sell, what is off limits, the proof they can use).
3. Paste the **Measured voice** block the tool printed under "What I sound
   like". Where the hand-written answers disagree with the measurement, say
   so: "You said short and punchy. Your posts average 19 words a sentence."
   The measurement wins unless the user says they are changing on purpose.
4. Save it to `~/.claude/linkedin/voice.md`.

## Checking a draft

`--check` scores a draft 0-100 against the profile and names the metric
furthest from the user. Hard flags (emoji when they never use one, an em dash
when they never write one, sentence case when they write lower-case, no
contractions when they always use them) cap the verdict at CLOSE.

`/li-preflight` runs this check automatically when the profile exists.

## Say this honestly

This is stylometry on a small sample, not identity verification. It catches
a draft that drifted into generic LinkedIn voice. It cannot tell you a post
is good. A post can match the voice perfectly and still have nothing in it.
