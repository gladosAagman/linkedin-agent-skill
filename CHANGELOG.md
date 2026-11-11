# Changelog

## [2.1.0] - 2026-11-09

### Added
- `/li-publish` with `publish.py`, opt-in: publishes an approved post to your
  own profile through LinkedIn's Posts API (`w_member_social`, "Share on
  LinkedIn" product) via a developer app you own. OAuth on a loopback-only
  callback with a constant-time state check; token stored owner-only, secret
  never stored. Every post needs `preview` first and a confirmation code
  bound to the exact text; pre-flight must say READY; no `{{placeholders}}`;
  no duplicates; 2 posts per 24 hours by default. Reserved characters are
  escaped for LinkedIn's little-text format and `#tags` become hashtag
  templates. Never comments, reacts, connects or messages.

### Changed
- README, CONTRIBUTING and SECURITY describe the one opt-in exception to
  "nothing posts".

## [2.0.0] - 2026-11-09

### Added
- `count.py` in `/li-post`: counts and lints posts, comments, invite notes,
  headlines and about sections, and draws what survives the mobile "see more"
  fold.
- `audit.py` in `/li-audit`: reads LinkedIn's `.xlsx` content export with no
  dependencies (merging the side-by-side "top posts" tables on URL), or CSV.
  Engagement rate, comment ratio, saves + sends, reach multiple, and grouped
  findings with n.
- `carousel.py` in `/li-carousel`: lints slide copy and builds the 1080x1350
  document, optionally printing the PDF through headless Chrome.
- `/li-voice` with `voice.py`, `/li-engage` with `targets.py`, and
  `/li-preflight` with `preflight.py`.
- `/li-newsletter`: newsletters and articles, from whether one should exist
  to the launch post.
- `/li-jobsearch`: recruiter-findable profile, target list, referrals and
  hiring-manager outreach before applications.
- `plan2ics.py` in `/li-plan`.
- Agents: `li-strategist` and `li-editor`.
- v2 sections in `/li-post`, `/li-audit`, `/li-carousel`, `/li-plan`,
  `/li-dm`, `/li-comment` and `/li-profile`.

### Infrastructure
- `scripts/validate.py`: checks the plugin manifests, every skill's and agent's
  frontmatter, every JSON and Python file, and that the README documents every
  skill and agent.
- `tests/`: regression tests that pin the v1 tools' documented behaviour, and
  unit tests for every v2 tool covering normal input and edge cases (empty
  input, malformed rows, boundaries, injection).
- GitHub Actions CI on Linux, macOS and Windows, Python 3.10 and 3.13.
- Installable as a Claude Code plugin: `marketplace.json` gained the `owner`
  field and `plugin.json` gained author, repository, homepage and license.
- MIT license, CONTRIBUTING.md, SECURITY.md.

### Preserved
Every v1 skill, tool, data file and template is unchanged in behaviour. The
first commit in this repository is v1 exactly as it was; every v2 change to
an existing skill is an added section marked "(v2)".

## [1.0.0]

The original eleven skills.
