---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:43ef09b52d5f2f61230b3cbd1d4033cec900824e2e7265bf19010a453d72bd52'
step_id: 'S52'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Run the exact-anchor Modelo 303 canonical-home census

## Scope

- `dev/registry/tests/test_m303_canonical_home_census.py`

## Description

- Consume the canonical semantic census, source-bound joiner, revision selector, and public official-casilla classifier without copying their logic.
- Prove exact parser plus DP30300 anchor totals of 406, 406, 426, 429, and 430 across the five epochs.
- Prove every mapped CasillaId agrees with the public classifier and box 46 reaches its canonical mapped owner without reverse-number inference.
- Preserve the two distinct DP30302 `110` anchors and prove a duplicate-anchor mutation refuses.
- Prove source constants, reserves, and fillers retain their truthful typed homes, including literal-byte and reserve-misclassification mutations.

## Outcome

Commit `636a1974f7` adds one test-only exact-anchor closure gate. Its 22 cases pass, as do the six existing exhaustive semantic-map and render-profile cases. Scoped Ruff, formatting, and diff checks are clean.

## Notes

No production code or registry data changed. A separate cross-package classifier test could not collect because peer wizard relocation temporarily removed `cadrumo.application.flows._capability`; that path does not overlap this Step or its focused evidence.
