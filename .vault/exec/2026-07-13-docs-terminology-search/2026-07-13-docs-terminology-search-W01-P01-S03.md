---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:bf6311b989cea42af27a3ee5ad7c74b05226457abfc9b52a221916b73ff93c66'
step_id: 'S03'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate

## Scope

- `dev/docs/terminology/_synonym_mining.py`
- `.vault/audit/`

## Description

- Read `src/cadrumo/_data/terminology/ratification/synonym-candidates.json`.
- Run `python -m dev.docs.terminology.synonyms validate`.

## Outcome

Queue is healthy: three candidates, each with an explicit status and
review reason (e.g. `prorateo` ratified as a hidden search form for
`prorrata`); validate reports clean. No unratified backlog; no action this
wave.

## Notes
