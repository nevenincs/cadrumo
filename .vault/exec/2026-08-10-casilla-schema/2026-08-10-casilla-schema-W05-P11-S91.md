---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:344e84663713e4706e0607a5b2fb59d7318906547b1c0328c63fda3bdff3eedc'
step_id: 'S91'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# adjudicate where the Modelo 303 deducible-IVA evidence gate binds - the ledger-to-casilla aggregation fold or the verify grant - since an unevidenced purchase now folds to zero at calculate while two committed modules still contract for the fold-then-block shape, then repair those modules against the adjudicated contract

## Scope

- `src/cadrumo/application/modelo/tests/test_modelo_303_deductible_evidence_gate.py`
- `src/cadrumo/application/modelo/tests/test_modelo_303_official_box_under_declaration.py`
- `src/cadrumo/application/aggregation/`

## Adjudication

Two distinct gates bind, on two different axes, and neither displaces the other.

The **aggregation** gate is the deduction CLASSIFICATION axis. An input-IVA row - `SOPORTADO` or `INVERSION_SUJETO_PASIVO`, excluding recargo de equivalencia - must carry an exact `IvaDeductionFactKind` and an immutable `IvaDeductionClassificationProvenance` before it can become an observation. A row without both is refused at the candidate boundary and dropped from the fold with the typed `MISSING_DEDUCTION_CLASSIFICATION` issue reason. This is deliberate, typed and surfaced, not a silent drop.

The **verify** gate is the DOCUMENT axis. It resolves the attached purchase-invoice evidence record and blocks the completeness grant when a deducible row has none, grounded in LIVA art. 97 and RD 1619/2012 art. 2.

A row can therefore carry a complete deduction classification and still have no attached invoice document. The fold-then-block-at-verify contract the two modules were written for is intact; what changed is that a row now needs its classification to be folded at all. No design question remained open, so no ADR was required and none was authored.

## Description

- Trace the zero deducible total to the aggregation candidate gate rather than to the verify gate, the prorrata branch, the revision split or the supply-nature classification, each of which was checked and excluded.
- Give the input-IVA ledger fixtures in both modules their exact deduction kind and provenance, on the outgoing leg only, so an output row cannot pick up deduction authority it must not carry.
- Wire the shared `general_m303_filing_evidence` fixture into the official-box calculate path, which every Modelo 303 revision now requires.
- Exclude projection-only casillas and the simplified-regime módulos unit casillas from the pull-path parity seeding, both of which the engine refuses as inputs outright.
- Retire the casilla-27 export-ref assertion whose subject was withdrawn corpus-wide, asserting the withdrawal itself so a restored layout reds the test and forces the assertion back.
- Absorb the same regression in the sibling bucket-aggregation flow module, which carried it identically and is outside the Step's named scope.

## Outcome

All three modules pass: the deducible-evidence gate 7 of 7, the official-box projection 7 of 7, and the bucket-aggregation flow 8 of 8. `ruff format --check` and `ruff check` pass on all three.

The scenario under test in the deducible-evidence module is unchanged. Its rows are still attached to no purchase-invoice evidence record, so the verify gate still has nothing to resolve and still blocks the grant; only the classification axis was completed. Naming the provenance authority `invoice_evidence` states which evidence family establishes the deduction kind, not that a document is on file.

The blast radius was wider than the Step's scope. The sibling bucket-aggregation module was red at HEAD with the identical signature and is not a casilla-schema surface; it was repaired here rather than left, per the standing absorb-in-scope-regressions mandate.

## Notes

The zero was diagnosed rather than guessed. The prorrata no-volume-data branch was compared across all six Modelo 303 revisions and is identical, so the revision split was excluded; the recent supply-nature and recipient-condition classification work was excluded because the output leg of the same fixture still folded correctly; and the verify-time evidence gate was excluded because it reads a different field. The candidate validator names the requirement outright - input IVA facts require exact deduction authority - and the transaction-level gate returns the typed issue.

This Step's commit could not land in-session: `.git/index.lock` has been held since 19:31:00 with a frozen mtime and no HEAD movement, a dead holder that blocks every staging operation in this worktree. Removing anything under `.git/` is absolutely forbidden, so it is reported rather than worked around. No data loss and no destructive Git operation occurred.
