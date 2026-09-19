---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:1d9467db8b37bd5c2a7bda2a0016195d2397238d933b839423647cb6b380f334'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S87 snapshot-bound row assembly independent review`

## Scope

Independent post-review of S87 across the mixed implementation commit
`8937f0cf548` and its scoped follow-on `a8f07f43af`. The review used
Vaultspec-RAG, exact-symbol confirmation, and whole-file reads of the row-set
assembler, calculation action, source mesh, calculation persistence, and the
canonical row identity and materialisation-provenance models.

The review checked that the snapshot command is a narrow authority-preserving
adapter to the existing grouping dispatcher; that it does not redeclare a
resolver, row carrier, provenance shape, store, or write path; that the
localized dispatcher refusals remain intact; and that the plan and execution
record do not close S88 through S91 by implication.

## Findings

### snapshot-delegation-mutation-bite | low | The initial test did not directly prove every delegated snapshot coordinate

The original behavioral test proved the current annual date and real dispatcher
result, but its assertion of the input snapshot revision identifier was not a
direct guard against a future wrapper that used a substitute revision. The
review added a narrow patched-dispatch test which requires the unchanged
`grouping`, `cells`, `snapshot.revision`, and `snapshot.filing_year` to reach
the existing dispatcher. Replacing either snapshot coordinate or inserting a
parallel assembly path now fails the focused test. The real-dispatch test and
the two localized-refusal tests remain independent evidence that the command
uses the live dispatcher behavior.

## Recommendations

No open S87 finding remains. Keep the command as the sole snapshot-bound
assembly adapter. S88 remains the Google-pull ingress owner, S89 remains the
owner of grouping, row index, binding identity, source identity, and fingerprint
carriage through a persisted calculation revision, S90 owns hostile ingress
validation, and S91 owns the real round trip. None of those later requirements
is implied by this checked S87 row.

The no-redeclaration audit is clean: `CalculationSourceResolution` remains the
single source-resolution envelope, `RowSourceIdentity` and
`DirectRowMaterializationProvenance` remain the single row-carrier models, and
`persist_calculation_revision` remains the only reviewed encrypted revision
writer. The new entry point delegates into the existing assembly module and has
no production caller yet, so it cannot silently represent a Google pull as live
calculation ingress.
