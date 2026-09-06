---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:ecf8d157cdff9f86d1d93ea7a4b2e668d724af601c3c7da5cbbf146001013dd6'
step_id: 'S37'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate the nine findings whose only reader is dev tooling, naming that reader in each, and make the naming falsifiable: the registry parity cluster cited a load-census classification module among the readers of eleven symbols when it names only the record_design_coverage module and consumes none of them, so the citation overstated the readership with nothing able to catch it because no gate reads evidence prose; gate that a cited path resolves and mentions a subject, while leaving an entry that cites no path alone since a legal default or an implementer class is a different honest shape

## Scope

- `dev/audit/tests/test_ledger_citations_resolve.py`

## Changes

- `A` `dev/audit/tests/test_ledger_citations_resolve.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests -m ""` -> `pass`

## Notes

`STATE_DIR` in `entrypoints/tui/devtools/fixture.py` was left unclassified. It
is dev-only by the same measurement, but sits under the `cadrumo.entrypoints.tui`
prefix both ratchets defer to that campaign.
