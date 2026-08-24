---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:114efd3c866662eb320488c60aea3c1518b9715f50ac5ca5394fab80b693b206'
step_id: 'S61'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Require distinct official offset-probe identities and emitted byte positions in live filing-export acceptance, and prove duplicate probes cannot inflate checked-offset evidence with a mutation bite.

## Scope

- `dev/registry/filing_export_proof.py`
- `dev/registry/tests/test_filing_export_live_proof.py`

## Description

- Reject repeated `(record_id, field_id)` official-probe identities when a live proof entry is constructed.
- Track every emitted byte covered by a probe and refuse probes whose verified byte ranges overlap.
- Add direct duplicate-identity and overlapping-position acceptance regressions over the loaded Modelo 200 layout.
- Disable the position-overlap guard temporarily and confirm the overlap regression fails, then restore the guard.

## Outcome

Checked-offset evidence can no longer report repeated probes as independent official positions. A valid entry must name distinct official fields, and acceptance verifies that those fields cover disjoint emitted-byte positions before their literal values can contribute evidence.

Focused verification passed:

- `uv run --no-sync ruff check dev/registry/filing_export_proof.py dev/registry/tests/test_filing_export_live_proof.py`
- `uv run --no-sync pytest -n 0 -q dev/registry/tests/test_filing_export_live_proof.py`: 11 passed.

## Notes

The mutation bite temporarily changed the emitted-position guard to false. The overlap regression then failed because evaluation reached the second literal mismatch instead of the expected distinct-position refusal. The guard was restored before the focused passing run. No production evidence entry was authored or broadened.
