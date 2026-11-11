---
name: li-jobsearch
description: >-
  Run a job search on LinkedIn the way hiring actually works - a profile that
  shows up in recruiter search, a target list of companies and people,
  outreach to hiring managers and referrers instead of mass applying, and
  replies to recruiters that get the facts. Use when the user says "I'm job
  hunting", "find me a job", "optimize my profile for recruiters", "open to
  work", "message a hiring manager", "ask for a referral", or "how do I reply
  to this recruiter".
---

# li-jobsearch

Mass applying is the default and it is the worst-performing option. One-click
applications land in a pile of hundreds. A referral or a message to the
hiring manager lands in front of a person. This skill builds the second kind
of search and keeps the user out of the first.

## Before anything, get the target

Ask, in one batched question:

1. **The role**, in the words job postings use. Two titles at most.
2. **The level, the location or remote, and the floor** on compensation.
3. **Ten to twenty companies** they would actually say yes to.
4. **Proof:** two or three outcomes from recent roles, with numbers. The
   skill never invents one. Without them, every draft comes back with
   `{{your number}}` in it.

## 1. Be findable

Recruiters search by title, skills and location. Run `/li-profile` with the
target role in mind, then check:

- **Headline:** the target title, word for word, then what changes when they
  hire you. `../li-post/count.py --kind headline` for length.
- **About:** the first two lines say the role and the proof.
- **Experience:** outcomes with numbers, in the job posting's vocabulary.
- **Skills:** the ten that appear most in the target postings, in that
  wording.
- **Open to Work:** say plainly what each setting shows. "Recruiters only"
  is visible to people using LinkedIn Recruiter, and LinkedIn says it takes
  steps to hide it from recruiters at the user's own company but cannot
  guarantee it. The public photo frame is visible to everyone. The user
  decides.

## 2. The target list

For each company: the likely hiring manager (the role the job reports to),
one person in the team, and anyone the user already knows there, first or
second degree. Ask the user to find these names on LinkedIn themselves. Do
not search or scrape on their behalf.

## 3. Outreach, in this order

- **A referral from someone they know.** Ask for the specific thing: "Would
  you be comfortable referring me for {role}? Here is the posting and three
  lines on why I fit." Make it easy to say yes and easy to say no.
- **The hiring manager.** A note or message with one specific reference to
  their team's work, one line of proof, one small ask. Write it with
  `/li-dm` and check it with `count.py --kind invite`.
- **The application**, after the message, not instead of it. Say in the
  message that they have applied.

Ten good messages a week beats a hundred applications. Never more than twenty
invites a day.

## 4. Recruiter replies

When a recruiter messages, ask the three things the message left out: the
compensation band, the level, and the location policy. If the role is wrong,
one line: not a fit, what would be, and a referral if the user knows someone.
`/li-inbox` triages a full inbox.

## 5. Posting while searching

Optional. If the user wants to, one post a week about the work they do, not
about the search, through `/li-post`. A post about looking for work is fine
once, written plainly, with the role and what they are good at. It is not a
weekly format.

## Never

- Never apply, message, connect or post on the user's behalf. Automated
  outreach violates LinkedIn's User Agreement.
- Never inflate a title, a date or a result. Background checks exist, and
  so does the hiring manager's memory.
- Never fabricate a mutual connection or a referral.
