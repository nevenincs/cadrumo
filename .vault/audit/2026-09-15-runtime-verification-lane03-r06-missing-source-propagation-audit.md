---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:8ff13652c6dd8a65263eb14b124dfc9a954525be9749b5112b0ed30d4fbddc43'
related:
  - "[[2026-09-15-runtime-verification-lane03-r05-absence-versus-zero-audit]]"
---

# `runtime-verification` audit: `lane03-r06 missing prior-year source propagation`

## Scope

Objective: trace the three modelo 720 prior-year valuation baseline bindings from production source-observation collection through their immediate consumer to user-visible readiness. The question is whether an absent prior-year filing stays distinguishable from explicit zero, with a focused repair authorised only if a consumer silently turns absence into zero or a complete result. Session `lane03-r06-missing-source-propagation`, coordinator only, no delegation.

Target: modelo `720`/2025/`0A` in the resolver lanes and `720`/2024/`0A` in the new test (the existing fidelity fixture years); source is the prior annual `720` filing. Bindings: `modelo-720-prior-year-cuentas-valoracion-baseline`, `modelo-720-prior-year-valores-valoracion-baseline`, `modelo-720-prior-year-inmuebles-valoracion-baseline`. Resolver evidence is reused from l03-r03-f01, l03-r04-f01 and l03-r05-f01 and was not re-run.

Checkout: branch `main`, HEAD `3082fdb05c5cfadb7dbd94bf30f0832f0f8684d0`, with a dirty worktree from concurrent contributors. Session window: 2026-09-15T20:07:39+02:00 to about 20:20+02:00.

## Findings

### l03-r06-f01 | low | Production chain for the 720 baselines

Observed, source-backed:

- **Observation supplier.** `persist_filed_revision_observation` (`src/cadrumo/application/modelo/filed_revision_observation.py:138`) projects a locally filed `CalculationRevision` into a `RegistryModeloObservation`. It saves the observation with non-official `source_kind = "app_filing"`, keyed by the work unit's `(modelo, filing_year, period)`. Live AEAT capture is a sibling writer into the same store.
- **Filed versus unfiled.** Only a filing transition writes the observation; a calculation alone does not. `source_kind` separates official AEAT evidence from `app_filing`.
- **Source selection.** `_gather_observations` (`src/cadrumo/application/calculations/binding_prefill.py:393`) walks `previous_filing_observation_requirements` and loads one observation per requirement key `(source_modelo, filing_year, period)` from the bucket-scoped encrypted store, passing it through the shared revision-stamp carry gate (`revision_carry_gate.py`).
- **Resolver.** `resolve_previous_filing_binding_values` is called at `binding_prefill.py:890`. An empty store short-circuits at `binding_prefill.py:877`.
- **Immediate consumer.** `resolve_bindings_from_local_store` (`binding_prefill.py:810`) builds a `BindingPrefillReport`. Its `unsatisfied` list is derived from the revision's declared previous-filing bindings minus the resolved key set (`binding_prefill.py:615`). This is where binding-result membership is checked.
- **Mesh projection.** `PreviousFilingSourceResolver.resolve` (`src/cadrumo/application/calculations/multi_year.py:70`) maps `unsatisfied` to `unresolved_binding_ids`, plus one `CalculationSourceDiagnostic` per binding (reason `unresolved_binding`) naming the source modelo, year and periods (`multi_year.py:106`–`:122`). It is enrolled as a mesh stage in `src/cadrumo/application/modelo/calculation_route.py:128`.
- **Presentation.** `calculate` renders source diagnostics as warning notices and ADVISORY lines (`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:187`, `:251`).
- **Readiness.** Verify runs `cross_period_clean_state_verdict_for_work_unit` (`src/cadrumo/application/modelo/verification_actions.py:498`). `evaluate_cross_period_clean_state` derives a previous-filing dependency for `720`/N-1/`0A` from the same registry requirements (`src/cadrumo/application/calculations/cross_period_clean_state.py:756`). A missing store row yields `MISSING_OBSERVATION` (`:1057`), a missing required casilla yields `MISSING_OBSERVED_CASILLA` (`:1097`), and every unclean dependency becomes a BLOCKING verification finding (`src/cadrumo/application/modelo/verification_cross_period.py:218`).

No registry casilla or formula in revision `2013-y-siguientes` references these bindings; they are listed only by construct `modelo-720-informative` and by dependency classification `modelo-720-dep-720` with treatment `factual_evidence`. The engine therefore has no casilla through which a missing baseline could default to zero.

### l03-r06-f02 | low | No production step converts an absent prior filing into zero or a complete result

Observed by source reading and confirmed by the focused test (l03-r06-f04):

- With no prior-year observation, the mesh returns empty `binding_values`, lists all three baselines in `unresolved_binding_ids`, and emits three `unresolved_binding` diagnostics naming `modelo 720 <N-1> 0A`. The verify clean-state dependency carries `MISSING_OBSERVATION` and the verdict is not clean.
- With a complete prior observation whose three valuations are explicitly zero, the mesh returns three `Decimal` zeros, nothing unresolved, and no `unresolved_binding` diagnostic. The clean-state dependency carries neither `MISSING_OBSERVATION` nor `MISSING_OBSERVED_CASILLA`, yet the verdict is still not clean. For the local `app_filing` source used here, the observed blocker was `MISSING_CURRENT_FILING_RECORD`.

No default, merge, prefill or calculation between resolver and readiness erases the missing state. The only zero substitution found is the explicit activity-start scope-out (`binding_prefill.py:840`–`:842`; clean-state `activity_start_date` scoping), which is a declared no-prior-obligation contract. The re-declaration projection `modelo_720_prior_baseline_observation` (`src/cadrumo/application/calculations/foreign_asset_redeclaration.py:621`) also skips absent bindings instead of fabricating a zero baseline (`:658`–`:660`). No product change was made.

### l03-r06-f03 | medium | The Modelo 720 re-declaration verify seam is a committed stub, so the baselines have no production value consumer

Observed: `modelo_720_redeclaration_findings` (`src/cadrumo/application/modelo/_m720_redeclaration_gate.py:33`) loads the selected revision, discards `work_unit`, `revision` and `observation_repository`, and returns `()`. It is still called from `verification_actions.py:746`. Commit `ee3d645ce5` (2026-09-12, "refactor(core): consolidate application boundaries and registry authority") replaced the previous implementation; the removed docstring already stated the advisory "cannot fire in production today" because no production caller supplies foreign-asset row evidence. The file is committed and unmodified in the worktree.

Consequence: `modelo_720_redeclaration_advisory_findings` and `modelo_720_prior_baseline_observation` have no production importer, and resolved baseline values feed no casilla, formula or verify finding. The existing test `src/cadrumo/adapters/persistence/profile/tests/test_modelo_720_redeclaration_e2e.py::test_advisory_fires_through_real_verify_for_the_omitted_grown_cuentas_position` fails on this checkout: `AssertionError: expected exactly one re-declaration advisory, got ()`. This is a pre-existing integration gap, not information loss between absence and zero, and it was outside this lane's repair authorisation.

### l03-r06-f04 | low | Focused consumer-boundary test added and passing

Change: I added `test_absent_prior_year_filing_stays_unresolved_and_blocking_while_explicit_zero_resolves` and two private helpers to `src/cadrumo/adapters/persistence/profile/tests/test_modelo_720_prior_year_baseline_fidelity.py`. Imports come directly from their defining modules. The test uses the real encrypted observation repository, the real `PreviousFilingSourceResolver` and the real `evaluate_cross_period_clean_state` in isolated runtime profiles, with synthetic observations only. It asserts the resolution membership, the `unresolved_binding` diagnostic coordinates, the clean-state blocker classification, and the non-clean verdict for both cases.

My first run expected `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` for the zero case. The verdict reported `MISSING_CURRENT_FILING_RECORD`, so that assertion failed; every other assertion before it passed. I did not copy the observed blocker into the test. The assertion was changed to the contract claim: a locally filed zero is supplied data but not filing-grade proof, so the verdict stays unclean with at least one blocker.

Verification, on Windows in PowerShell:

- `uv run --no-sync pytest -v -n0 -p no:cacheprovider <new test> <e2e advisory test>` exited 1 (2 failed): the new test on the wrong blocker expectation described above, and the pre-existing e2e advisory test (l03-r06-f03).
- `uv run --no-sync pytest -v -n0 -p no:cacheprovider <new test>` after the assertion change exited 0 (1 passed in 88.76s).
- `uv run --no-sync ruff check <file>` exited 0.
- `uv run --no-sync ruff format --check <file>` exited 0.
- `uv run --no-sync ty check <file>` exited 0.

The focused selection ran as a direct pytest node selection, not through a `just` lane recipe. No repository test lock mechanism was found in the root `conftest.py` or the `justfile`.

## Recommendations

Requiredness contract (from l03-r06-f02): the only applicability limits the clean state applies to this dependency are activity start date, the listed not-applicable source modelos, and explicit zero-value binding overrides. It has no Modelo 720 first-declarant rule, so a first-time 720 declarant with a recorded activity start before the prior year would be blocked on `MISSING_OBSERVATION`. Whether that is legally correct is an open question. It must be grounded in the official Modelo 720 obligation rules (RD 1065/2007 arts. 42-bis, 42-ter and 54-bis; Orden HAP/72/2013) before any semantic change, and it needs a decision, not a probe.

Integration gap (from l03-r06-f03): a follow-on decision must choose whether to restore a production Modelo 720 re-declaration verify path, which requires a durable foreign-asset evidence source, or to retire the stub, the advisory functions and the failing e2e test together.

Still unproven: CLI rendering of the `unresolved_binding` notice in a live `calculate` run; behaviour with official AEAT-sourced prior observations; competing observations; and filing-grade correctness.
