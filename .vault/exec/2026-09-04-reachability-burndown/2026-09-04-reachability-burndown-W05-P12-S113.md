---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:df59286f93738d93c150ebdcf4c03e017f738061b5b91ff06e7ea093a3db0c4c'
step_id: 'S113'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify the last unadjudicated unreachable module and verify the duplication campaign closed on adjudicated residue

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests/test_duplication_scan.py -m '' -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `pass`

## Notes

Every module the audit reports as unreachable now carries a ledger
classification. The last one was the per-action package a concurrent migration
is building; both the source and the destination of that move are dark at once,
which is the migration's midpoint rather than two separate findings.

The module ratchet is green over a narrower scope than the audit reports:
`frozen_prefixes` excludes `cadrumo.entrypoints.tui` entirely, on the stated
ground that the subtree is in-flight work owned elsewhere and the gate must not
depend on its classification holding still. That is a scope decision, not an
exemption, and it is left as its owner set it -- unfreezing would make the gate
fail on another contributor's churn. The subtree is covered instead by the
reachability ledger, which records a classification without requiring one to
hold still, and by the render-coverage ratchet added in the preceding step.

The duplication campaign is complete on its amended closure condition: the live
scan observes ten clone groups, the disposition record reconciles all ten as
nine cluster-owned plus one intentional, and reports zero actionable and zero
advisory residue. Its gate carries vacuity guards in both directions -- an
unavailable scan cannot read as full coverage, and the record may not declare
fewer groups than the scan observes. Plan completion is 20 of 20.
