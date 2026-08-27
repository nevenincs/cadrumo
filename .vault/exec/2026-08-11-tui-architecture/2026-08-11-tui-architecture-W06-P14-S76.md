---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:6300b45e948e7a75506f371dcf6c23513f06a58ed7710a3b03551cf7dd2ac07d'
step_id: 'S76'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Remove frontend-owned manager callbacks and consume registered operation APIs and application results only

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` TUI boundary sweep over all 67 cli/_config modules -> `0 violations`

## Notes

Verified rather than implemented. The cited module no longer exists: a single
earlier change retired it along with the censo review UI surface, taking twelve
hundred lines of frontend-owned callbacks with it and reducing the dispatch
module to a hundred and thirty lines.

What remains is a CLI projection: the dispatcher wraps a wizard command with an
output-language activation and an error boundary, and reads its flow from the
core wizard catalogue. No frontend is constructed and no callback is owned here.

Plan-versus-code discrepancy, recorded because the row's second clause is not
literally what shipped. The row asks that the surface consume registered
operation APIs and application results only; the dispatcher consumes a core
wizard-catalogue flow instead. With the callbacks module deleted there is no
subject left for that clause, and the frontend-neutrality it exists to secure
holds. Code wins.

The whole `cli/_config` surface is swept by the TUI boundary detector, so a
reintroduced frontend reach in any of its sixty-seven modules reds by name.
