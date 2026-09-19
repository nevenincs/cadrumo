---
tags:
  - '#plan'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_hash: 'sha256:77575301edb98d0a5fdd9cf1f23b201ecb506353343faffcae9f8488fd61071c'
tier: L2
related:
  - '[[2026-08-01-filing-period-casilla-channel-adr]]'
  - '[[2026-08-01-filing-period-casilla-channel-audit]]'
---
# `filing-period-casilla-channel` plan

Carry the AEAT period token on the typed text channel, close the literal-membership dispatch class, refresh the goldens, and unblock the docs publish.

## Description

This plan executes `2026-08-01-filing-period-casilla-channel-adr`, grounded in
`2026-08-01-filing-period-casilla-channel-audit`. The `decl.periodo` casilla
moves from the quarter ordinal on the Decimal channel to the canonical period
token (`1T`, `EXT-1T`) on the typed text-scalar channel, adopting the
uncommitted three-package routing set already in the working tree. No persisted
model shape changes: `casilla_values` stays Decimal-valued and the token rides
the existing `input_values_by_casilla_id` string channel. The pre-release
regime applies - a stale ordinal-bearing revision refuses loudly at draft
build and is recalculated, never migrated. P01 delivers the atomic fix commit,
P02 closes the remaining literal-membership sites, P03 refreshes the goldens
and unblocks the publish, P04 opens the named follow-ups as tracked items.

## Steps

### Phase `P01` - land the token and the typed routing as one atomic commit

Deliver the period-token fill, the adopted three-package typed-scalar routing set, the replay adjustment, and every dependent test update as a single explicit-pathspec commit so HEAD stays importable.

- [x] `P01.S01` - Verify working-tree ownership of the uncommitted typed-scalar routing set with the owning campaign and adopt it unchanged rather than re-authoring it; `src/cadrumo/application/filing/__init__.py`.
- [x] `P01.S02` - Supply period.registry_token for the filing_period semantic role on the string channel, keeping filing_year on the Decimal channel; `src/cadrumo/application/modelo/_binding_resolution.py`.
- [x] `P01.S03` - Thread the resolved period token through the engine text_inputs channel so it persists in input_values_by_casilla_id; `src/cadrumo/application/modelo/_calculation_resolution.py`.
- [x] `P01.S04` - Verify the replay merge precedence already favours the string channel for the filing-period token (no code change was required); `src/cadrumo/application/modelo/_revision_replay_inputs.py`.
- [x] `P01.S05` - Update the parametrised ordinal pins to assert the token on the string channel; `src/cadrumo/application/modelo/tests/test_declaration_period_binding.py`.
- [x] `P01.S06` - Update the two conditional-formula-trace tests refused by the typed text channel; `src/cadrumo/application/filing/tests/test_build_draft_conditional_formula_trace.py`.
- [x] `P01.S07` - Populate the CalculationRevision roundtrip fixture with a non-default period_code entry in input_values_by_casilla_id; `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`.
- [x] `P01.S08` - Add the anti-tautology proof that an ordinal-shaped persisted period value is refused loudly at draft build; `src/cadrumo/application/filing/tests/test_text_casilla_routing.py`.
- [x] `P01.S09` - Observe clean collect-only and land the whole set as one explicit-pathspec commit; `src/cadrumo`.

### Phase `P02` - close the literal-membership class beyond the filing builder

Fix the calculate-boundary override routing, retire the dead ordinal projection, and reconcile the predicate-validator text gates to family-derived membership.

- [x] `P02.S10` - Derive the calculate-boundary override text-channel membership from registry_scalar_value_type instead of the text literal; `src/cadrumo/application/modelo/_calculate_input.py`.
- [x] `P02.S11` - Retire declaration_period_ordinal and its ordinal table with their tests (zero production consumers confirmed at HEAD, no sweep needed); `src/cadrumo/core/_period.py`.
- [x] `P02.S12` - Reconcile the casilla_equals predicate text gates to family-derived membership with instructive refusals; `src/cadrumo/domain/calculations/registry/_validate_verification_predicates.py`.

### Phase `P03` - refresh goldens and unblock the docs publish

Move the committed cli-sequence goldens from the ordinal to the token and prove the strict docs build green so the authorised publish can proceed.

- [x] `P03.S13` - Refresh the cli-sequence goldens moving decl.periodo values 1 through 4 to 1T through 4T across the 54 occurrences; `docs/_sequences`.
- [x] `P03.S14` - Prove the strict docs build and documented-command conformance gates green and report the publish unblocked; `dev/docs/tests/test_docs_build.py`.

### Phase `P04` - track the named follow-ups

Open the deferred work as explicit tracked items per the operator's issues-over-latent-drift directive.

- [x] `P04.S15` - Open a tracked issue for the observation channel's type-expressiveness gap: strictly-Decimal CasillaObservation.value cannot express text-family values and emits a plausible-looking structural Decimal zero for them instead; `.vault/audit/2026-08-01-filing-period-casilla-channel-audit.md`.
- [x] `P04.S16` - Confirm with the M369 landing campaign that the token fill unblocks EXT-period validation and hand the end-to-end coverage back to it; `src/cadrumo/_data/registry/aeat/modelos/369`.

## Parallelization

P01 is strictly sequential and lands as one commit: its steps are edits to one
coherent change set and MUST NOT be split across commits (the application layer
does not import without the registry additions). P02 depends on P01 (it imports
the taxonomy helper P01 lands) but its three steps are independent of each
other. P03 depends on P01 only and may run in parallel with P02. P04 may run at
any time after the ADR is accepted.

## Verification

- The filing draft for a 1T Modelo 303 work unit carries `decl.periodo` as
  `1T`, validated through `_validate_period_code`, and the M369 EXT quarters
  build without a ModeloError from the ordinal projection.
- `casilla_values` remains `Mapping[CasillaId, Decimal]` and
  `CasillaObservation.value` remains `Decimal` - no union widening lands.
- The `application/filing` package suite passes with zero failures, including
  the two previously failing conditional-formula-trace tests.
- The anti-tautology proof fails when the build-gate refusal is removed
  (mutation flips the result, not merely kills the fixture).
- No production site keys a string-family membership filter on
  `data_type == "text"` - confirmed by rg over `src/cadrumo` excluding tests.
- The strict docs build exits 0 and the cli-sequence goldens carry `1T`-`4T`
  for `decl.periodo`, after which the coordinator is told the publish is
  unblocked.
- Follow-up items exist as tracked issues, each naming this plan's stem.
- The plan is complete when every Step is closed with a matching exec record.
