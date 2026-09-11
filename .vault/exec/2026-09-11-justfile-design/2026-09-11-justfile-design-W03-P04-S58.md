---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:37967966b9d637983e7d79ca1af4dfb93dcd2ff57cc471c5823e6d93a9de1ea4'
step_id: 'S58'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Decide whether resident-service-marked tests are removed reclassified or explicitly outside public population accounting

## Scope

- `dev/docs`

## Changes

- `M` `dev/docs/preprocess/tests/test_golden_queries.py`
- `M` `dev/tests/test_lane_reachability.py`
- `verify:` `uv run --no-sync pytest -q --collect-only -n0 --confcutdir=dev/docs/preprocess/tests -m resident_service dev/docs/preprocess/tests/test_golden_queries.py dev/docs/terminology/tests/test_sweep_live_service.py` -> `pass`

## Notes

Resident-service tests remain outside public population accounting for W05's
RAG recipe removal; the pure workbook-classification test is reclassified into
repository contracts.
