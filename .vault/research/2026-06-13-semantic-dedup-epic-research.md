---
tags:
  - '#research'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-semantic-dedup-epic-adr]]'
---

# `semantic-dedup-epic` research: investigation backing the decision

This research captures the investigation that backed the `semantic-dedup-epic` ADR.

## Findings

Discovery Pass 1 of the codebase semantic-deduplication epic confirmed three
duplication clusters needing a canonical-home decision before any removal lands: F1
tax-id validation, F2 fichero-BOE money formatting, and F3 repository bucket-id
resolution.

Applying the substitutability pre-filter (a site is consolidated only when the
canonical site's constraint shape is a superset of the candidate's), two of the three
clusters fail on close reading despite strong lexical/semantic clustering — the
false-positive pattern the pre-filter exists to catch. The fichero-BOE surface
additionally carries fixed-width/encoding constraints that forbid an autonomous merge.
The findings establish that only the genuinely substitutable cluster is safe to
consolidate; the others are recorded as constraint-shape-divergent and left in place.
