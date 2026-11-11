---
name: li-newsletter
description: >-
  Plan and write a LinkedIn newsletter or article - the title that earns the
  subscribe, the issue structure, the cover, the feed post that launches each
  issue, and a cadence the user can keep. Use when the user says "LinkedIn
  newsletter", "write an article", "long-form on LinkedIn", "start a
  newsletter", "turn this into an issue", or has an idea too big for a post.
---

# li-newsletter

When feed reach drops, the subscriber list is the part of LinkedIn the user
owns the most of. A newsletter subscriber is notified when a new issue goes
out, which a follower is not. The trade is that an issue is a commitment: a
newsletter that stops after issue three is worse than none.

## Before writing, decide whether it should exist

Ask, in one batched question:

1. **The promise.** One sentence: who it is for and what they get every
   issue. "Ops notes for 10-50 person agencies, one fix per issue."
2. **The cadence they can keep for six months.** Weekly, fortnightly or
   monthly. Pick the slowest one they would still be proud of.
3. **Three issue topics they could write today.** If they cannot name three,
   it is a post, not a newsletter. Hand it to `/li-post`.

## The title and description

The newsletter's name and its one-line description are what people see on
the subscribe prompt. Name the reader or the outcome, not the author:
"The Agency Ops Fix" beats "Thoughts from Sarah". The description says what
an issue contains and how often, in the reader's words.

## The issue

```
TITLE       the specific promise of this issue, under ~70 characters
COVER       a 1920x1080 image, one line of text at most, readable small
OPENING     2-3 sentences: the problem, in the reader's words, and the payoff
BODY        sections with subheads, 600-1,200 words. One idea, worked through.
            Short paragraphs. A number, a screenshot or a template in each section.
THE TAKEAWAY one thing to do this week, in one paragraph
CLOSE       what the next issue is about, so the subscribe has a reason
```

Run the title through `../li-post/count.py --kind headline` for length, and
the whole draft through `/li-human`. Long-form shows slop more than posts do,
because readers stay long enough to notice the pattern.

## The launch post

Every issue needs a feed post, because subscribers are not the only audience.
Write it with `/li-post`: the hook is the issue's best single idea, stated in
full, not "my new newsletter is out". The link goes in the first comment. Run
it through `/li-preflight`.

## Cadence and the plan

Put the issue day in `/li-plan` as its own slot and do not post a second
long piece that week. `plan2ics.py` in `/li-plan` will put it on the
calendar.

## Never

- Never publish, schedule or send the issue. The user publishes it in
  LinkedIn's editor.
- Never invent a statistic, a case study or a quote to fill a section. If a
  section needs a number the user does not have, it comes back with
  `{{your number}}` and a flag.
