---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:89af83a5cfa144a056e476f7d783981925e8472c385115fa32442953bee3d2c7'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---

# `modelo-parity-rollup` audit: `Luna Max parity tranche code review`

## Scope

Reviewed the accepted five-domain parity ADR, the denominator research, the L3 execution plan, and the bounded Luna Max changes for exact annual-coordinate measurement, casilla producer/formula closure, and M100 2024 external-oracle enrollment.

Owned surfaces reviewed were `dev/registry/conformance/manager.py`, `dev/tests/test_registry_conformance_cli.py`, `src/cadrumo/domain/calculations/registry/_schema.py`, `src/cadrumo/domain/calculations/registry/_validate.py`, `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py`, and the M100 2024 verification expectation declaration. Unrelated contribuyente and profile worktree changes were preserved and treated as peer-owned.

## Findings

### peer-profile-gate | high | Current shared registry validation is blocked by an unrelated profile-schema edit

The current validated registry cannot load `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`: `sections.20.fields.2.description` exceeds the Pydantic 512-character limit. This exact failure blocks the fresh replay of the new validator tests, validated conformance fixtures, `report`, `coverage`, and `audit --check`. The profile and contribuyente edits are outside this tranche and were not changed. The worker-era gates remain separately attributed; current shared-state acceptance is not green until the profile owner resolves or explicitly gates that failure.

### annual-matrix-boundary | medium | The annual matrix is honest but currently contains only the provisional D2025 coordinate

The new typed matrix keeps the 73-modelo/90-revision portfolio separate, resolves M100 exercise 2025 period `0A` through the law-selected revision, and exposes all six classifications including zero counts. It does not yet compare any coordinate with an official annual layout, and the remaining portfolio is not silently represented as parity. This is the correct bounded outcome for W01.P03.S01, but it is not schema-parity closure.

### reverse-wiring-replay | medium | Current shared-state tests cannot re-certify the new producer invariant

The implementation adds a lossless producer inventory and validator failures for computed casillas without a formula producer and non-computed casillas with formula declarations. Existing validator checks retain exact formula identity, duplicate-target, and dangling-direction coverage. The worker reported 7 focused tests and 263 broader registry tests passing before the peer profile edit; the current replay shows 1 unaffected inventory test passing and 6 wiring tests failing before reaching the invariant because the profile schema cannot load. No formula, profile, relation, or model data was changed by this tranche.

### oracle-enrollment-boundary | medium | M100 2024 oracle enrollment is exact but current full replay remains unverified

The declaration adds only `0513` and `0514` to the existing M100 2024 externally grounded set. The bundled AEAT manual payloads provide one-to-one values for the Asturias and Rioja scenarios (`4550.00` and `5200.00) in both casillas); the Valencian payload deliberately grounds `0513` only. The worker reported 21 integration tests, 15 strict-payload tests, 90 revisions, 24 payloads, zero unattributed payloads, zero findings, and 61 declared grounded casillas before the peer profile edit. A fresh full replay was not possible after that edit. Valencian `0514` and the unmodelled `6550` case remain deferred.

### peer-profile-retest | low | The peer profile gate is green after its owner repair

A fresh bounded replay after the peer-owned schema repair reports 153 profile tests passed, 18 conformance-profile tests passed, one parity-coverage test passed, and `coverage --json` reports `registry_validated=true` with 90 of 90 rows without required-tier gaps. The earlier high-severity shared-state blocker is therefore closed for the current replay. Full repository tests and full-project typing remain unverified.

### construct-source-gap | medium | Coverage remains revision-level and lacks selector or producer evidence projection

The current coverage surface reports the required legal, official-source, and layout evidence floor for all 90 revisions, but it does not enumerate construct-level provenance for each formula, parameter, binding, relation, selector, or producer. Formula, parameter, binding, relation, and casilla records carry references; selectors lack an independent evidence-reference contract. No projection was added because doing so would require a new contract and could convert a revision-level floor into a false per-construct claim.

### post-peer-parity-replay | low | The bounded parity-owned replay is green after the peer repair

The current shared-state replay passes 7 casilla wiring tests, 87 conformance CLI tests, and 3 external-grounding integration tests. `audit --check` passes with zero ratchet, vacuity, progress, grounding, attribution, and unmatched-evidence violations. Coverage reports 61 independently checked casillas out of 1,261, 61 declared grounding claims, 24 oracle payloads, and 90 of 90 rows without required legal/source/layout evidence gaps. This closes the temporary replay blocker but does not close the annual official-layout or construct-level provenance gaps.

## Recommendations

- Have the profile owner resolve the 512-character schema violation, then replay the current-state registry validator tests, conformance CLI tests, `report --json`, `coverage --json`, and `audit --check`. Preserve the exact owner-surface failure if it remains.
- Keep W01.P03 open for the official annual-layout comparator and explicit missing/extra/attribute divergences; do not convert the provisional D2025 matrix into a portfolio parity claim.
- Keep W01.P04 closed only after the reverse-wiring tests replay against a valid shared registry. The invariant must continue to fail in both directions and must not be bypassed with test doubles or validation shortcuts.
- Accept the M100 2024 `0513`/`0514` enrollment as a bounded evidence improvement, while retaining the stated Valencian and M100 focus-row deferrals.
- Do not advance to semantic M100 changes or bulk cross-model parity work until the baseline is green and each next step has its own RAG grounding, disjoint ownership, and real verification record. The current bounded baseline is green for profile and coverage surfaces; replay the parity-owned validator and conformance tests before closing their held steps.
