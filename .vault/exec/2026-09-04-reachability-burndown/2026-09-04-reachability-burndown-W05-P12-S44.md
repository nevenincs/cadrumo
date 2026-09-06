---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:5c42cad67de00e9cd3184adc3b67cfb3829adf0f089ce13a7c819830960621b6'
step_id: 'S44'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate the two custody families: the envelope-level recovery unlock and envelope parser are superseded because the live recovery artifact path calls the field-level unlock material primitive and derives the wrapper AAD through the field-level helper, and a crypto divergence was ruled out first by confirming the envelope AAD form delegates to that same helper so the bypass changes no bytes; and the summary-witness load with the data-file replace are what remains of the committed custody read side after its reader trio was removed, leaving a live write side that commits data the product can neither read back as a witness nor replace

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The committed-custody entry is now the fourth instance of provisioned
persistence with no consumer, after the ledger import door, the repair
remediation decisions, and this package's own reader trio. The write side here
is live, so custody data is committed that the product cannot read back as a
summary witness or replace.
