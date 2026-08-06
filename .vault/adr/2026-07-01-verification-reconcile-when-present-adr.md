---
tags:
  - '#adr'
  - '#verification-reconcile-when-present'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:111b8786222fee599993ac8796550dccc1442e8f43246c0b51eac2fee7a552b7'
related:
  - '[[2026-07-01-verification-contract-coverage-audit]]'
  - '[[2026-07-06-verification-reconcile-when-present-research]]'
---
# `verification-reconcile-when-present` adr: `reconcile-when-present verification class` | (**status:** `accepted`)

## Problem Statement

The directive "write the verification contract for every modelo and casilla not
yet enrolled" could not be satisfied by registry edits. The verify gate folds all
of a revision's `verification_expectations` into ONE
`RegistryVerificationPolicy` (`_schema.py:verification_policy`):
`computed_casilla_ids` is the UNION across expectations (a single coverage
denominator) and `min_coverage = max(...)`. `_verify.py` sets
`coverage = |covered ∩ provided| / |computed_casilla_ids|` and refuses the filing
(`NEEDS_REVIEW`) when `coverage < min_coverage`. Every shipped contract sets
`min_coverage = 1`. So enrolling any additional computed casilla the extraction
does not always print lowers coverage below 100% and flips a legitimate filing
from VERIFIED to NEEDS_REVIEW. There was no low-`min_coverage` escape hatch: a
second expectation at `min_coverage = "0"` still folds to `max(1, 0) = 1` against
the enlarged union denominator. The coverage-contract mechanism therefore
structurally forbade enrolling the ~892 situational computed casillas (dominated
by ~867 Modelo 100 Renta casillas), documented in the
`verification-contract-coverage` audit as a critical finding.

## Considerations

A verification expectation asserts two independent things about a casilla:
(1) its value should be reconciled against the engine when the filing prints it,
and (2) the filing is only complete if it prints the casilla (coverage). For an
always-present final (cuota íntegra, cuota diferencial) both hold. For a
situational casilla (a negative-result carryforward, a per-rate cuota, a rate) only
(1) holds — demanding its presence (2) breaks legitimate filings that omit it. The
gate conflated the two into one `computed_casilla_ids` axis.

## Considered options

- **A. Per-modelo `min_coverage` recalibration.** Lower each revision's
  `min_coverage` so the enlarged set fits. Rejected: it weakens the always-present
  finals gate (a filing missing a genuine final would silently pass), violating
  `no-silent-under-declaration`.
- **B. Leave the situational casillas unenrolled (status quo).** Rejected: it
  leaves ~892 computed casillas with no filed-vs-engine reconciliation — a silent
  verification hole — and does not satisfy the directive.
- **C (chosen). A `reconcile_when_present` casilla class.** Split axis (1) from
  axis (2): a new expectation field enrolls casillas that are value-reconciled
  WHEN present but EXCLUDED from the coverage denominator. Enrolling a situational
  casilla here can never lower coverage, so it is always safe; every computed
  casilla becomes reconcilable without touching any coverage-gated verdict.

## Constraints

- Non-regression: no legitimate filing's verdict may change. Coverage must remain
  a function of `computed_casilla_ids` only; the reconcile-when-present set never
  enters the denominator.
- `reconcile_when_present_casilla_ids` must be disjoint from
  `computed_casilla_ids` on the same expectation, unique, and reference real
  casilla ids (registry-build validated).
- Grounding: each reconcile-when-present enrollment reuses its revision's existing
  verification-expectation `legal_refs`/`source_refs` (the same AEAT Diseño de
  Registros / framework law), per `registry-calculation-legal-grounding` — no
  fabricated grounding.

## Implementation

Note on convergence: a parallel campaign independently landed the schema half of
this class at HEAD — `VerificationExpectationDefinition.reconcile_when_present_casilla_ids`,
the `RegistryVerificationPolicy` fold, and the `_validate_surfaces.py` unknown-casilla
check — but left the field DORMANT: HEAD's `_verify.py` reconciled only
`computed_casilla_ids`, so the declared/folded field was never consumed (the
`no-dormant-source-resolvers` smell). This change completes it and enrolls against it.

- Schema (pre-existing at HEAD via convergent peer commit):
  `reconcile_when_present_casilla_ids: tuple[CasillaId, ...] = ()` with a uniqueness
  validator and a model validator enforcing disjointness from
  `computed_casilla_ids`; `RegistryVerificationPolicy` folds
  `reconcile_when_present_casilla_ids: frozenset[CasillaId]` as the union across
  expectations while `computed_casilla_ids`, `tolerance`, and `min_coverage` fold
  unchanged.
- Gate wiring (this change, `_verify.py`): reconcile a casilla when it is in
  `computed_casilla_ids ∪ reconcile_when_present_casilla_ids`; `_compute_coverage`
  is unchanged (`policy.computed_casilla_ids` only), so coverage and status are
  bit-for-bit identical for every existing contract. This activates the dormant
  field.
- Reference validation (this change, `_validate_references.py`): the new field is
  `chk_tuple`-checked against real casilla ids, complementing the HEAD
  `_validate_surfaces.py` unknown-casilla check.
- Enrollment: one `reconcile-when-present` fragment per gap revision (16 revisions,
  892 casillas) enrolls every computed-but-unenrolled casilla at
  `computed_casilla_ids = []`, `min_coverage = "0"`, grounded from the revision's
  existing expectation.
- Gates: `test_every_computed_casilla_enrolled.py` (completeness invariant — every
  computed casilla is enrolled, and stays enrolled as new casillas are authored),
  and `test_reconcile_when_present_casilla_surfaces_a_present_divergence` (the
  class actually reconciles a present divergent value, not a no-op). The existing
  M130 verify test confirms coverage stays 1.0 / VERIFIED with the class present.

## Rationale

Splitting reconcile-from-coverage is the minimal change that makes exhaustive
enrollment SAFE by construction: because the reconcile-when-present set is excluded
from the coverage denominator, no enrollment can flip a coverage verdict, so the
"every casilla" invariant is tenable without a per-casilla coverage recalibration
campaign. Reconciling a filed value against the engine is non-tautological — the
filed value is external (printed by AEAT / entered by the taxpayer) — so surfacing
a filed-vs-engine divergence is a genuine, actionable finding, aligned with
`no-silent-under-declaration` (surface, do not silently pass). The verdict effect
is advisory (`NEEDS_REVIEW`), never a live-filing action, honoring
`aeat-safety-legal-gates`.

## Consequences

- Every computed casilla across every revision is now reconciled filed-vs-engine
  when present; the completeness gate keeps the surface exhaustive.
- A reconcile-when-present casilla whose engine model is incomplete will surface a
  divergence on a real filing that prints it, flipping that filing to
  NEEDS_REVIEW. This is the intended signal — it points the operator at a real
  modelled-vs-filed disagreement — but it means engine-model gaps now become
  visible through verification. Any such divergence surfaced by a real fixture is
  an engine-grounding follow-up (absorbed in-scope), not a reason to unenroll.
- `min_coverage` and the always-present finals gate are unchanged; no existing
  VERIFIED filing regresses (proven by the verification suite).
