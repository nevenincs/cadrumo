---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:aeb8eec741ad269a5949ed0f6846985c12197a16d207a6be8e8880a29ffa97c0'
step_id: 'S10'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# add a curated API boundary overview

## Scope

- `docs/api/index.md`

## Description

Verified `docs/api/index.md` landed via commit `64b5a8a45d` as the curated Python API
boundary overview: a contributor-facing "Python API overview" page describing the
hexagonal layer boundaries (`cadrumo.core`, `cadrumo.domain`, `cadrumo.application`,
`cadrumo.adapters`, `cadrumo.entrypoints`) and a "Where to start" reading order, each
layer cross-linked with `{doc}` roles into the generated module reference. Confirmed
`python -m dev.docs.apidocs scaffold --check` reports "Stub tree is conformant. No
drift detected." - the curated page sits outside the CLI-owned generated `*.rst` stub
set and does not conflict with it.

## Outcome

Step closed. Evidence: `docs/api/index.md` present at HEAD with the curated overview
content; apidocs scaffold conformance clean; nitpicky Sphinx build green including this
page (see `S14`/team lead's confirmed run).

## Notes

No new commit required for this verification; the page itself shipped in `64b5a8a45d`.
