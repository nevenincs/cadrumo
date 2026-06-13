---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S19'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P06.S19`

Identified the next modelo-family fragmentation target from committed file-size
and revision-count evidence before touching registry TOMLs.

- Reviewed: `src/aeat/_data/registry/aeat/modelos`
- Modified: `.vault/plan/2026-05-22-schema-hardening-plan.md`

## Description

M131 is the next fragmentation target.

Evidence from tracked TOML files:

- M131 has the largest remaining tracked TOML file:
  `modelos/131/revisions/2026.toml` at 1,746 lines.
- M131 has three of the six largest remaining tracked TOML files:
  2026 at 1,746 lines, 2024 at 1,654 lines, and 2025 at 1,599 lines.
- M131 is directory-mode but still uses four `revision_file` revisions and zero
  `fragment_directory` revisions.
- The current reviewability gate caps TOML fragments at 1,750 lines, so the
  M131 2026 revision has only four lines of headroom.

Non-targets for the next slice:

- M100 and M200 have high total line counts, but both already use
  fragment-directory revisions.
- M303 is already a fragment-directory layout.
- M130 is the next large single file at 1,653 lines, but it has one revision;
  it is a lower priority than M131's four near-threshold revision files.

The next implementation slice should split M131 revisions into
`revisions/<id>/revision.toml` plus topic fragments using the generic loader
path. It should not introduce per-modelo loader behavior.

## Tests

The evidence command used tracked TOML files from `git ls-files`, counted lines
and row lengths, and inferred revision source shape from committed paths. No
registry TOML files were modified in this step.
