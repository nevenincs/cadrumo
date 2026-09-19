---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:0cd37df36c6998061780bc51f02c64f3ee09371a379329584954cc69e32e910d'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---

# `casilla-schema` audit: `S27 modelo.requires classifier review`

## Scope

Formal review of `W03.P07.S27` against the accepted read-model and canonical-
derivations decisions. The review covered the classifier, strict payload and
CLI projection, advisory construction, four locale additions, and the focused
real-registry tests. It checked canonical primary-plus-alternate row identity,
source-bucket truthfulness, unbucketed advisory behavior, absence of invented
actions or remote-AEAT implications, single-authority reuse, and test integrity.

Verification reran the four focused integration tests, Ruff check, Ruff format
check, and strict BasedPyright over the classifier and its direct test. All
passed. The initial pytest invocation inherited the unit-only marker expression
and selected zero tests; the explicit integration rerun executed four tests.

## Findings

### atribucion-profile-source | medium | A profile-backed source is labelled as a live observation

`_LIVE_OBSERVATION_SOURCE_KINDS` in
`src/cadrumo/application/modelo/_data_inventory.py` includes
`BindingSourceKind.ATRIBUCION_MEMBER`, so every bound M184 attribution-member
row is emitted under `live_observation`. The production owner
`AtribucionMemberSourceResolver` in
`src/cadrumo/application/aggregation/_atribucion_member.py` instead loads
`UserProfileRecord` facts from the active taxpayer profile and identifies
itself as `atribucion_member_profile`. This contradicts the bucket contract,
which distinguishes `profile_derivable` from the observation, register, and
invoice-backed `live_observation` sources. The current focused test exercises
M390 register-backed rows but has no M184 assertion, so the semantic
misclassification passes all S27 gates and gives an operator the wrong source
to prepare.

## Recommendations

- Repair `atribucion-profile-source` by removing `ATRIBUCION_MEMBER` from the
  live-observation set and routing it through the existing profile-derived
  semantics, including canonical profile-readiness facts where available. If
  that readiness projection cannot yet represent the repeated socio rows,
  preserve the source in `unbucketed_sources` with the existing action-free
  advisory until the profile projection is extended; do not label it as an
  observation.
- Add a real bundled-registry M184 regression asserting each canonical
  attribution-member binding pair appears exactly once and does not appear in
  `live_observation`. Keep the existing M100 alternate-binding and M390 local-
  store coverage.

## Correction and resolution

The original finding correctly identified a semantic mismatch in the
classifier set, but overstated its current runtime effect. A direct probe of
the bundled M184 2025 snapshot found four `atribucion_member` binding
declarations and zero pairs returned by `bound_casilla_binding_ids`. Therefore
the phrase "every bound M184 attribution-member row" was factually wrong: no
such bound casilla row exists in the current corpus, the classifier could not
emit one, and the recommended exact-pair CLI regression was impossible. The
finding was preventive taxonomy hardening, not evidence of a currently
mislabelled operator row.

Commit `b20a786869` removes `ATRIBUCION_MEMBER` from
`_LIVE_OBSERVATION_SOURCE_KINDS`. The focused production-backed regression
imports `AtribucionMemberSourceResolver`, confirms its real `owned_sources`
declaration, and proves that declaration remains disjoint from the classifier
set. This is the correct gate for a source family whose registry bindings are
row bindings rather than bound-casilla pairs.

Re-review verification passed: four focused application tests, four focused
CLI integration tests, Ruff check, Ruff format check, and strict BasedPyright
over the classifier and its application test. The diff is limited to the
intended source-set removal and its focused test within the S27 repair surface;
unrelated shared-worktree changes were not reviewed or modified.

The finding is resolved. Final S27 verdict: PASS with no remaining findings.
