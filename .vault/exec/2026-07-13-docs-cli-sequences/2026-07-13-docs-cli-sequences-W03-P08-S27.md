---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:e1084adcbd7955f34a608b0303b10e49ee62f034572fc2582eef8a4fd6b67994'
step_id: 'S27'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Wire the pytest gate calling the same engine check functions so CI catches golden drift without a full docs build

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Extend `dev/docs/tests/test_sequence_goldens.py` with `TestCommittedGoldensCleanGate`, importing the facade `check_sequences` and calling it unscoped over the committed `docs/` tree.
- Assert the returned problem tuple is empty; on failure print every problem verbatim (each already names page, sequence, frame, argv, and diff).
- Leave the existing S18 executor mask-honesty tests untouched.

## Outcome

The pytest half of the two-surfaces-one-engine gate now catches golden drift on the same `check_sequences` execution path the Sphinx `builder-inited` hook wires, without a full docs build. Passes green (`-m "integration and docs"`, the module's marker lane) in ~4.5s with zero enrolled sequences today; scales with the enrolled surface as sequences land.

## Notes

The module carries `pytest.mark.integration`; the default addopts marker filter deselects it unless `-m integration` is passed, matching the existing S18 tests' CI lane.
