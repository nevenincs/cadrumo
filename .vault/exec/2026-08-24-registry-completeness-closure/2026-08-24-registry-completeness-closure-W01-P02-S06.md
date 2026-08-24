---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a43fb051e8131cc56f7048861499dbe3c1a31fc15ac9891019bb04ac5091f637'
step_id: 'S06'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Define strict typed per-revision closure-limb and refusal models on the application registry boundary

## Scope

- `src/cadrumo/application/registry/`

## Description

- Add immutable typed models for per-revision closure limbs, evidence provenance, accountable dispositions, and refusal reasons.
- Require evidence for a satisfied limb and an owning, reconsiderable refusal for every unsatisfied or unmeasured limb.
- Expose the closure contract through the application-registry facade and generate its API-reference stub.
- Add focused contract tests for fail-closed outcomes, evidence uniqueness, ownership matching, strictness, and immutability.

## Outcome

The application boundary now has one strict model vocabulary for the three closure limbs. A composer cannot present a satisfied limb without evidence, omit accountability for a refusal, or relabel an unmeasured limb as an ordinary refusal.

Verification passed:

- `pytest -n0 src/cadrumo/application/registry/tests/test_closure_models.py`  -  5 passed.
- `ruff check src/cadrumo/application/registry/__init__.py src/cadrumo/application/registry/_closure.py src/cadrumo/application/registry/tests/test_closure_models.py`  -  passed.
- `ty check src/cadrumo/application/registry/_closure.py`  -  passed.
- `python -m dev.docs.apidocs scaffold --check`  -  no drift.

## Notes

The API scaffold regenerated unrelated peer stubs as well; only the closure module stub and its parent toctree entry belong to this Step.
