---
tags:
  - '#audit'
  - '#modelo-130-100-continuity'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:704374b89637f939ebd269441b8a0d87bbf7ff18d04224cf125ef299965fec6a'
related:
  - "[[2026-06-10-modelo-130-100-continuity-plan]]"
---

# `modelo-130-100-continuity` audit: `P03 S06 review`

## Scope

Reviewed the remaining `P03.S06` verification step for the M130-to-M100 annual continuity plan. The audit covered current registry routing, live application tests, declaration reconciliation mismatch behavior, relation-prefill missing-quarter behavior, and official AEAT routing evidence for M100 casilla 0604.

## Findings

### p03-s06-review | low | Numeric AEAT worked example not located

Current official AEAT pages confirm that pagos fraccionados for economic activities are carried to M100 casilla 0604, and the official Modelo 100 form labels 0604 as pagos fraccionados ingresados. The search did not locate a numeric AEAT worked example that explicitly carries four M130 quarterly casilla-19 values into M100 0604. The accepted verification oracle is therefore structural: M100 0604 must equal the persisted quarterly M130 observations, and the filed-declaration reconciliation must flag any different 0604 with typed legal/source provenance.

### p03-s06-review | low | M100 pagos-fraccionados continuity verified on focused gates

The focused gates passed: live fold-in and full ledger-to-M130-to-M100 vertical tests passed 9/9; mismatch and missing-quarter non-silent tests passed 2/2; historical registry pagos-fraccionados wiring passed 4/4; ruff passed for the touched verification surfaces. After the concurrent declaration-reconcile source slice landed in commit `2b59a9fa06`, the current-year parser/reconcile/fold-in group passed 17/17, the parser-chain group passed 7/7, the ledger/relation/historical group passed 10/10, and ruff passed again. Later concurrent commits `ef6e1e71d8` and `d323fb1558` did not touch the scoped M100 pagos-fraccionados continuity/reconcile surfaces. The mismatch path is non-silent because a filed declaracion with a different 0604 produces a typed casilla mismatch carrying legal and source refs.

### p03-s06-review | low | Current-year declaration extraction now covers 0604

The 2024/2025 M100 declaration profiles now include `0604`, and the committed synthetic
current-year declaration fixtures parse that casilla for both years. This closes the
current annual declaration evidence path used by P03.S06: the parser can surface the filed
`0604`, and the post-filing reconcile can compare it against the persisted annual revision.

### p03-s06-review | low | Historical declaration extraction remains future backfill

The 2021-2023 M100 revisions declare `0604` in `reconcile_when_present`, and the historical
registry relation contract is covered by existing tests, but the legacy real-corpus declaration
profiles do not currently extract `0604`. That is not a regression in this current-year closure
because `reconcile_when_present` only compares values present on both sides. Deferred follow-up
`modelo-100-historical-0604-declaration-profile-backfill` should add real-corpus extraction for
2021-2023 if historical filed-declaration reconciliation needs the same `0604` coverage.

## Recommendations

- Close `P03.S06` with the evidence limitation above. Do not invent a numeric AEAT oracle for 0604 until an official worked example is found.
- Keep future Renta annual payment-credit tests structural: seed or compute distinct prior-period filed observations and assert the annual relation transports those exact values with provenance.
- Track `modelo-100-historical-0604-declaration-profile-backfill` separately from this current
  2024/2025 declaration-reconcile closure.
