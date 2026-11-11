# The LinkedIn agent skill

[![CI](https://github.com/gladosAagman/linkedin-agent-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/gladosAagman/linkedin-agent-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Seventeen Claude skills and two agents that run a LinkedIn account. No signup,
no API key, nothing to connect.

One of them writes your posts off 21 hook formulas. One comments on other
people's posts. One handles the replies under yours. One scores your profile
out of 100 and rewrites what lost points. One plans the week: what to post,
when, and who to engage with.

And one is the humanizer, which is the reason the rest are usable. It strips
the em dashes, the slop vocabulary and the invisible watermark characters out
of a draft, then scores what is left against a five-check detection panel
before you ever see it.

New in v2, because reach has fallen and the third-party analytics people
relied on keep going dark: an audit that reads LinkedIn's own `.xlsx` export
on your machine, a counter that draws exactly what survives the "see more"
fold, a carousel builder that produces the PDF, a voice profiler measured
from your own posts (LinkedIn holds back posts that read as low-effort AI),
an engagement ledger, a newsletter playbook, a job-search playbook, and one
pre-flight command that runs every check at once.

**Nothing gets posted until you say yes.** These skills write. You post.

## Install

**As a Claude Code plugin** (skills and agents together):

```
/plugin marketplace add gladosAagman/linkedin-agent-skill
/plugin install linkedin-agent@linkedin-agent-skill
```

**Or copy the skill folders** into your Claude skills directory:

```bash
cp -r skills/li-* ~/.claude/skills/
```

Project-local instead of global: copy the same folders into your repo's
`.claude/skills/`. No Claude Code at all? Paste any single `SKILL.md` at the
top of a chat and it runs as a mode - you lose the Python tools, which is
most of the point of `/li-human`, `/li-audit` and `/li-preflight`, but the
rest works.

Then spend ten minutes on `templates/voice.md`. Copy it to
`~/.claude/linkedin/voice.md` and fill it in, or paste three of your own posts
into Claude and say "write my voice.md from these". Every skill reads that
file. Skip it and everything comes out sounding like everyone else. Better:
run `/li-voice` on ten of your own posts and it fills the file from evidence.

## The seventeen

| command | what it does |
| --- | --- |
| `/li-post` | One idea into a post. Three hook options from [21 formulas](skills/li-post/hooks.json), one full draft, humanized before you see it. |
| `/li-comment` | Comments on other people's posts. Nine types, picked by what the post actually is. Never "Great post!". |
| `/li-reply` | The thread under your own post. Sorts every comment into lead / substance / peer / support / noise, then writes in that order. |
| `/li-profile` | Scores your profile against a [12-part rubric](skills/li-profile/rubric.json) out of 100, then rewrites in fix-first order. |
| `/li-plan` | The week. What to post, when to post it, and the 10 people to engage with. Writes `~/.claude/linkedin/plan.md`. |
| `/li-human` | The humanizer. Two scripts that actually run. See below. |
| `/li-carousel` | Document posts. Slide-by-slide copy, the cover that earns the swipe, and the PDF to upload. |
| `/li-repurpose` | One video, newsletter or transcript into a week of posts that each stand alone. |
| `/li-dm` | The 200-character invite note, the first message, and the two follow-ups. Two. |
| `/li-inbox` | Triages the inbox into lead / recruiter / peer / ask / spam, and tells you which tell gave the sequence away. |
| `/li-audit` | Post-mortem on what you have already published. Ranks by engagement rate and reach multiple, not impressions. **v2:** `audit.py` reads LinkedIn's `.xlsx` export directly. |
| `/li-voice` | **New.** Measures your voice from your own posts and flags a draft that drifted into generic LinkedIn voice. |
| `/li-engage` | **New.** The engagement ledger: who you commented on, the share your top three took, the reach / peer / buyer mix, and who is overdue. |
| `/li-preflight` | **New.** Counter, humanizer panel and voice check on one draft. One READY or FIX FIRST. |
| `/li-newsletter` | **New.** Newsletters and articles: whether it should exist, the title, the issue structure, the launch post, a cadence you can keep. |
| `/li-publish` | **New in 2.1, opt-in.** Publishes an approved post to your own profile through LinkedIn's official API, only with a confirmation code tied to the exact previewed text. Setup below. |
| `/li-jobsearch` | **New.** A job search the way hiring works: findable by recruiters, a target list, referrals and hiring managers before applications, recruiter replies. |

`/li-post`, `/li-carousel`, `/li-plan`, `/li-dm`, `/li-comment` and
`/li-profile` gained tools in v2 too: see below.

## The two agents

| agent | what it does |
| --- | --- |
| `li-strategist` | Runs the weekly loop: your export through the audit, the engagement ledger, then next week's plan, roster and calendar. |
| `li-editor` | Takes any draft and returns it ready to paste: humanized, counted, voice-checked, with the pre-flight table. |

## The humanizer

`/li-human` ships two Python scripts with no dependencies. They run on your
machine, on your text, and nothing is uploaded.

```bash
python3 humanize.py draft.txt --report      # clean it, show every change
python3 detect.py draft.txt                  # score it, five checks
python3 detect.py before.txt after.txt       # prove the delta
```

**What comes out automatically:**

- **Invisible characters.** Zero-width spaces and joiners, word joiners, soft
  hyphens, byte-order marks, Unicode tag characters, non-breaking and narrow
  spaces. Your keyboard does not make these. They survive copy-paste and they
  are invisible in every editor you own.
- **Typography.** Em dash to comma, en dash to hyphen, curly quotes to
  straight, ellipsis to three dots.
- **The lexicon.** 113 stock words and phrases with plain-English
  replacements - delve, leverage, robust, seamless, crucial, testament to, "in
  today's fast-paced world", "let that sink in" - with capitalisation preserved
  and URLs untouched. It lives in
  [`slop.json`](skills/li-human/slop.json) and it is meant to be edited.

**What gets flagged instead of fixed:** "It's not just X, it's Y", rule-of-three
triads, one-word rhetorical questions, hashtag walls, reflex engagement bait,
uniform sentence length. Changing the shape of a sentence needs judgement, so
those are handed back for a rewrite rather than mangled by a regex.

**The five checks**, scored 0-100, higher is more human:

| check | what it measures |
| --- | --- |
| BURSTINESS | sentence-length variation. Models write even. |
| SPECIFICITY | numbers, names and concrete markers per 100 words |
| SLOP DENSITY | lexicon hits per 100 words |
| FINGERPRINT | invisible characters, em dashes, curly quotes per 1,000 |
| VOICE | contractions, person, structural tells |

The verdict weights the mean at 60% and the **weakest single check** at 40%,
because a detector only needs one signal to fire.

Run against a deliberately terrible draft:

```
  BURSTINESS    ##################......  73.0
  SPECIFICITY   ######################## 100.0
  SLOP DENSITY  ........................   0.0    19 stock terms, 24.1 per 100 words
  FINGERPRINT   ........................   0.0    1 invisible, 1 em dash, 3 curly quote
  VOICE         ########................  33.3    3 structural tells
  ------------------------------------------------------------
  HUMAN SCORE   ######..................  24.8   FLAGGED
```

After `humanize.py`, with the flagged structures still unrewritten:

```
  HUMAN SCORE   #################.......  69.7   REVIEW    (+44.9)
```

The last stretch to PASS is the part the script deliberately leaves to you.

## The v2 tools

Eight more scripts, same rules: Python 3 standard library, run on your
machine, nothing uploaded.

```bash
python3 skills/li-post/count.py draft.txt                       # count + lint, draws the "see more" fold
python3 skills/li-post/count.py note.txt --kind invite          # also: comment, headline, about
python3 skills/li-audit/audit.py Content_export.xlsx --followers 4200
python3 skills/li-carousel/carousel.py slides.txt --handle "Sarah Chen" --pdf deck.pdf
python3 skills/li-plan/plan2ics.py ~/.claude/linkedin/plan.md -o week.ics
python3 skills/li-voice/voice.py samples.txt --save ~/.claude/linkedin/voice.json
python3 skills/li-engage/targets.py report
python3 skills/li-preflight/preflight.py draft.txt
```

### What the feed actually shows

`count.py` counts the way a browser text box does and lints against the
pack's rules: the limit for each surface (post 3,000, comment 1,250, invite
200, headline 220, about 2,600), a link in the body, more than three
hashtags, walls of text, reflex bait, stock comment openers, "Helping..."
headlines and em dashes. For posts it draws the mobile fold:

```
  WHAT THE FEED SHOWS ON A PHONE, BEFORE "...see more"
  +------------------------------------------------------+
  | Writing a proposal used to take me 5 hours. It now   |
  | takes 20 minutes, and I didn't buy a single tool to  |
  | get there.                                           |
  |                                                      |
  | Here's what changed. I st                            |
  +----------------------------------------- ...see more +

  NOTE  LENGTH      774 / 3,000. The working range for a text post is 900-1,300.
  PASS  FIRST LINE  113 characters, survives the mobile fold
  PASS  LINKS       none in the body
  PASS  HASHTAGS    0
  PASS  WALL        no paragraph over three phone lines
```

### Your own analytics, which cannot go dark

`audit.py` reads the Content export (`.xlsx`, with no dependencies), or a CSV,
or a sheet made by hand. It finds the sheet with an Impressions column and
merges the side-by-side "top posts" tables on the post URL. It ranks by
engagement rate with comment ratio, saves + sends per 1,000 and reach
multiple, and reports any group (length, link in body, hashtags, format,
question hooks) 1.4x above or below the rest, with n:

```
WHAT THE DATA SAYS
  1. link = no link: 4.0% vs 0.9% for everything else (4.3x, above). n=18, solid.
  Day of week shows nothing. Stop optimising it.
```

(That output is from a synthetic test file, not anyone's real account.)

### Carousels to PDF

`carousel.py` lints slide copy (8-12 slides, a cover of six words or fewer,
3-7 word headlines, 25 words of body at most, a recap slide that is a list)
and writes a 1080x1350 HTML document with numbered pages and your handle on
each. With `--pdf` it prints it through headless Chrome if you have it.

### Voice, engagement, calendar, pre-flight

`voice.py` measures sentence rhythm, contractions, person, casing, emoji and
your recurring words from your own posts, then scores drafts against that
range. `targets.py` is the engagement ledger behind `/li-engage`.
`plan2ics.py` turns the weekly plan into calendar reminders. `preflight.py`
runs the counter, the humanizer panel and the voice check together:

```
PRE-FLIGHT  ·  post
============================================================
  COUNT  PASS  774 / 3,000
  HUMAN  PASS  77.6 PASS
  VOICE  SKIP  no profile. Run /li-voice once to measure yours.
------------------------------------------------------------
  READY
```

## Publishing from Claude (opt-in, 2.1)

If you would rather not paste, `/li-publish` posts through LinkedIn's
official API. One-time setup, about ten minutes, done by you:

1. <https://www.linkedin.com/developers/apps> -> **Create app** (LinkedIn asks
   for a Page to associate it with).
2. **Products**: add **Share on LinkedIn** and **Sign In with LinkedIn using
   OpenID Connect**.
3. **Auth**: add the redirect URL `http://localhost:8765/callback`.
4. In your terminal: `python3 skills/li-publish/publish.py auth`. It asks for
   the Client ID and Secret (hidden), opens LinkedIn's sign-in page, and
   stores only the token, owner-readable, in `~/.claude/linkedin/`.

Then every post goes `preview` -> you say yes -> `post --confirm <code>`:

```bash
python3 skills/li-publish/publish.py preview draft.txt
python3 skills/li-publish/publish.py post draft.txt --confirm 3f9a1c0be2
```

Never paste your Client Secret or token into a chat. The token lasts about 60
days; `publish.py status` warns before it runs out.

## The fine print, which is the honest part

**These skills do not post to LinkedIn, with one opt-in exception.** There is no
official API for posting to a personal profile without an approved partner
app, and automating the site with a browser or a third-party tool violates
[LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement) and
gets accounts restricted. So every skill here ends the same way: a copy-ready
block, and you paste it. That is not a limitation bolted on afterwards, it is
the design. It is also why the approval gate is real rather than a setting.

The exception, added in 2.1, is `/li-publish`, and it uses the official
route instead of a workaround: LinkedIn's Posts API with the
`w_member_social` permission, through a developer app you create and own
with the "Share on LinkedIn" product. It publishes one post at a time, only
after `preview` shows you the exact text and only with the confirmation code
derived from that text, after pre-flight says READY, never a duplicate, at
most two a day by default. It never comments, reacts, connects or messages.
Those stay manual, because automating them is what gets accounts restricted.

**The five checks are local heuristics, not detector APIs.** They are modelled
on the signals public detectors key on, and they run entirely on your machine.
They are not GPTZero, Originality, Copyleaks, Winston or Turnitin, they do not
call those services, and they cannot promise those verdicts. Fixing what they
measure tends to move those numbers, because they are measuring the same
underlying things. That is the whole claim. Nobody can honestly sell you
"undetectable", and anybody who does is selling you something.

**The invisible-character pass is real and it is narrow.** It removes the
zero-width and format characters that end up in generated text and survive a
copy-paste. That is a genuine, checkable fingerprint. It is not a claim about
defeating a cryptographic watermarking scheme, and this repo does not make
one.

**Nothing here fabricates.** No invented metrics, clients or outcomes go under
your name. If a draft needs a number you have not given, it comes back with
`{{your number}}` in it and a flag, every time.

## Files

```
skills/li-post/hooks.json        21 hook formulas: template, example, what it is for, how it gets ruined
skills/li-human/slop.json        the lexicon: 113 terms, 17 invisible classes, 11 structural tells
skills/li-human/humanize.py      the three cleaning passes
skills/li-human/detect.py        the five-check panel
skills/li-profile/rubric.json    the 100-point profile score
skills/li-post/count.py          counter + lints for post, comment, invite, headline, about   v2
skills/li-audit/audit.py         analytics export (.xlsx / .csv) -> what worked, with n        v2
skills/li-carousel/carousel.py   slide copy -> linted 1080x1350 HTML / PDF                     v2
skills/li-plan/plan2ics.py       the plan as calendar reminders (.ics)                         v2
skills/li-voice/voice.py         voice profile from your own posts, and the drift check        v2
skills/li-engage/targets.py      the engagement ledger                                         v2
skills/li-preflight/preflight.py counter + humanizer + voice, one verdict                      v2
skills/li-publish/publish.py     opt-in publishing through the official API, approval-gated   2.1
agents/li-strategist.md          the weekly loop, end to end                                   v2
agents/li-editor.md              any draft to ready-to-paste                                   v2
scripts/validate.py              structural checks, run in CI                                  v2
tests/                           regression tests for v1, unit tests for v2                    v2
templates/voice.md               your voice profile. Fill this in first.
```

Your own files live in `~/.claude/linkedin/`: `voice.md`, `voice.json`,
`plan.md`, `log.md`, `roster.txt` and `engage.csv`, plus `credentials.json`
and `published.jsonl` if you turn on `/li-publish`.

## Development

```bash
python3 scripts/validate.py              # skills, agents, manifests, JSON, README coverage
python3 -m unittest discover -s tests    # no network
```

CI runs both on Linux, macOS and Windows. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the rules a pull request has to keep and [CHANGELOG.md](CHANGELOG.md) for
what changed.

## License

[MIT](LICENSE).
