---
tags:
  - '#plan'
  - '#ledger-filter-period'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-filter-period-adr]]'
  - '[[2026-06-10-ledger-filter-period-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `ledger-filter-period` `Ledger shared period filter: ratify, delete residual notation, continuity gate` plan

### Phase `P01` - Ratify single boundary authority

Pin Period.contains() as the one shared filter authority for both the CLI ledger filter and the modelo calculation snapshot; add a regression guard that forbids parallel boundary implementations.

- [x] `P01.S01` - Write a boundary-authority pin test asserting Period.contains() is the sole filter path for both the CLI and the calc engine; `src/aeat/application/aggregation/tests/test_period_boundary_authority.py`.
- [x] `P01.S02` - Assert that the CLI filter path and the calc-engine path both produce an identical Period object for the same (year, AEAT-token) input; `src/aeat/application/aggregation/tests/test_period_boundary_authority.py`.

### Phase `P02` - Delete internal legacy aliases

Remove the Q1-Q4, A, ANUAL, ANNUAL dead branches from aggregation_period_for_modelo and confirm the four call sites already pass canonical StandardPeriodCode tokens.

- [x] `P02.S03` - Confirm the four aggregation_period_for_modelo call sites pass canonical StandardPeriodCode tokens via CalculationSourceContext.period; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `P02.S04` - Delete the Q1-Q4, A, ANUAL, ANNUAL legacy alias branches from aggregation_period_for_modelo; `src/aeat/application/aggregation/_modelo_bindings.py:448-453`.
- [x] `P02.S05` - Add a test asserting aggregation_period_for_modelo raises on the deleted tokens and succeeds on every canonical StandardPeriodCode span member; `src/aeat/application/aggregation/tests/test_aggregation_period_for_modelo.py`.

### Phase `P03` - Migrate stale test call sites

Rewrite the six broken test call sites to the canonical year-qualified AEAT-token form so the ledger-filter suite is green.

- [x] `P03.S06` - Migrate test_ledger_corpus_journeys.py:378 and test_ledger_persona_autonoma_close.py:113 from 2025Q1 to 2025-1T; `src/aeat/application/aggregation/tests/test_ledger_corpus_journeys.py, src/aeat/application/aggregation/tests/test_ledger_persona_autonoma_close.py`.
- [x] `P03.S07` - Migrate test_ledger_persona_yearend_m100.py:126/277/279 from bare 2025/2026 to 2025-0A/2026-0A; `src/aeat/application/aggregation/tests/test_ledger_persona_yearend_m100.py`.
- [x] `P03.S08` - Migrate test_ledger_list_filter.py:93-96,135 from bare YYYY to f'{year}-0A' canonical year-qualified form; `src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py`.
- [x] `P03.S09` - Run the full ledger-filter test suite and confirm zero failures after the six migrations; `src/aeat/application/aggregation/tests/, src/aeat/entrypoints/cli/tests/`.

### Phase `P04` - Period continuity invariant and secure-storage gate

Add the anti-double-count continuity invariant test covering every adjacent quarter and month pair across two or more years, and assert the encrypted-storage boundary invariant.

- [x] `P04.S10` - Write the period-continuity invariant test: for every adjacent quarter pair and adjacent month pair across 2+ years assert prior.end + 1 day == next.start and no date is contained by both; `src/aeat/application/aggregation/tests/test_period_continuity.py`.
- [x] `P04.S11` - Assert the encrypted-storage invariant: the period filter selects rows from SecureObjectRepository without adding any plaintext persistence surface; `src/aeat/application/aggregation/tests/test_period_boundary_authority.py`.

### Phase `P05` - Reconcile sibling typed-Period test churn

Absorb the two CLI persona-test failures the parallel typed-core-Period refactor (W02.P08) introduced in files this plan's P03 migration touched. Worked concurrently with the typed-Period and ledger-amount-direction agents; fixes are applied as targeted, single-purpose test-contract updates that match the landed typed-Period production contracts, never reverting peer WIP.

- [x] `P05.S12` - Update test_no_annual_money_rollup_surface_exists to assert the ledger status period payload as the typed-Period object {filing_year, code} the W02.P08 refactor now serialises, replacing the bare-year string; `src/aeat/entrypoints/cli/tests/test_ledger_persona_yearend_m100.py`.
- [x] `P05.S13` - Pass a typed core.Period to derive_work_unit_id and WorkUnit in test_modification_refused_when_row_feeds_finalized_modelo, which now require typed Period (coordinated with the ledger-amount-direction agent co-editing the file); `src/aeat/entrypoints/cli/tests/test_ledger_corpus_journeys.py`.

## Description

This plan executes the three cleanup concerns documented in the ADR (2026-06-10-ledger-filter-period-adr) that remain after the strict `year.period` AEAT-token grammar landed in commit `7c150c749`.

The canonical `year.period` grammar — enforced by `_canonical_period`, `_filter_canonical_period`, `_ledger_aeat_token`, and `_aeat_token_to_calendar` in `src/aeat/entrypoints/cli/_common.py` — already resolves to `Period.model_validate()` + `Period.contains()` in `src/aeat/application/aggregation/_models.py` for both the CLI ledger filter and the modelo calculation snapshot. The boundary is single-authority by construction; this plan ratifies that fact with a pinning test, removes the residual dead notation beneath the operator surface, migrates the six broken test call sites, and adds the missing anti-double-count continuity invariant.

Every Step targets a specific ADR decision: P01 ratifies decision 1 (single shared filter authority); P02 enacts decision 2 (delete `Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL` aliases from `aggregation_period_for_modelo` at `_modelo_bindings.py:448-453`); P03 enacts decision 3 (migrate the six stale test sites); P04 enacts decisions 4 and 6 (continuity gate and secure-storage assertion).

`no-legacy-compatibility` applies: the alias branches are deleted outright with zero deprecation, not bridged. Every caller already passes a canonical `StandardPeriodCode` token, so no caller normalisation is needed.

Cross-cluster note: `project_ledger_list` at `src/aeat/entrypoints/cli/_ledger_list.py:41` is the shared injection point with cluster C5 (sort applies after filter at that call site) and with cluster C7 (the same period predicate selects `source_transaction_ids` for the participation index). Any future change to the period boundary MUST be made once at `Period.contains()`, never re-derived. The C5 sort Step MUST rebase onto this filter signature unchanged.

## Parallelization

P01 (boundary-authority pin test) MUST land before P02 and P03; it creates the test file that subsequent phases reference and confirms the ratification premise.

P02 (alias deletion) and P03 (test migration) are independent and may execute in parallel once P01 is closed. P02.S03 (call-site audit) MUST precede P02.S04 (deletion) within P02; P02.S05 (regression guard) MUST follow P02.S04. P03 steps may run in any order among themselves; P03.S09 (suite green gate) MUST be the last step of P03 and blocks P04.

P04 (continuity + secure-storage) runs last; it depends on P03.S09 confirming a green suite so the new invariant tests are meaningful additions, not masked by pre-existing failures.

The boundary mutation surface is `Period.contains()` alone. No Phase touches the CLI helper chain (`_common.py`) or the upstream context constructors; all work is inside `_modelo_bindings.py` (deletion), test files (migration and new tests), and the new test module. Parallel P02/P03 execution is therefore safe: they touch disjoint files.

## Verification

The plan is complete when all of the following checks pass with zero failures:

- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_period_boundary_authority.py -v` - the boundary-authority pin test passes; both the CLI path and calc-engine path produce identical `Period` objects for the same `(year, AEAT-token)` input.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_aggregation_period_for_modelo.py -v` - the deletion regression guard passes; `aggregation_period_for_modelo` raises on `Q1`, `Q2`, `Q3`, `Q4`, `A`, `ANUAL`, `ANNUAL` and succeeds on all canonical `StandardPeriodCode` span members.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_period_continuity.py -v` - the continuity invariant passes; for every adjacent quarter and adjacent month pair across at least two years: `prior.end + timedelta(days=1) == next.start` and no calendar date is `contains()`-ed by both periods.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/ src/aeat/entrypoints/cli/tests/ -q --tb=short` - the full ledger-filter suite is green; no test that was green before this plan regresses and the six previously broken test sites now pass.
- `git grep -E "(2025Q1|2026Q1|period=['\"]?[0-9]{4}['\"])" src/aeat/` returns zero matches on the six migrated test files - no residual stale notation.
- `git grep -E "(\"Q1\"|\"Q2\"|\"Q3\"|\"Q4\"|\"ANUAL\"|\"ANNUAL\")" src/aeat/application/aggregation/_modelo_bindings.py` returns zero matches - the legacy aliases are deleted.
- `uv run --no-sync vaultspec-core vault check all` exits clean for the `ledger-filter-period` feature.
