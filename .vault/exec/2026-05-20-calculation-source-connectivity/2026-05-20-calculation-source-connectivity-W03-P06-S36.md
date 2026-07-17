---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S36'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# [RETIRED] Derive Renta source region from TaxResidenceProfile CCAA

## Reconciliation outcome

Retired on 2026-07-17. The profile read, region plumbing, and injectable
override path existed only to activate an empty regional category layer in
synthetic tests. They were removed while preserving real registry-backed
state-law deductibility. The material below is historical execution evidence,
not current architecture.

## Scope

- `src/aeat/application/aggregation/_renta_ledger.py`

## Description

- Derive the ordinary-residence comunidad autonoma at the Renta expense aggregation boundary: `aggregate_renta_ledger_expenses_from_repositories` now reads the bucket's active user profile (`tax_residence.ccaa`), parses it with `parse_tax_region`, and threads the resulting `CCAA` into the inner `aggregate_renta_ledger_expenses` call.
- Fail closed: an absent profile, an absent `tax_residence.ccaa` fact, or a foral / otherwise unparseable region resolves to `None`, so the aggregation falls through to the state year profile (D4).
- Add a private `_resolve_residence_ccaa` helper that loads the profile through the public `UserProfileLifecycleRepository` facade (lazy import, `ProfileNotFoundError` caught) and accepts an optional injected `UserProfileRecord` for testing.
- Expose `profile_record` and `region_category_overrides` as optional injectable parameters on the wrapper (mirroring the existing repository injection and the inner function's signature) so the wire is testable end-to-end without mocks.
- Complete the accepted `renta-region-deductibility` ADR mechanism: the context axis (S33), year+CCAA profile lookup (S34), region registry profiles (S35), and the byte-identical/selection domain tests (S37/S38) had already landed; this is the last caller-side wire making the territorial-regime axis reachable from the production source-mesh resolver (`LedgerRentaExpenseAggregationSourceResolver`).

## Outcome

- The territorial-regime residence axis is now reachable end-to-end from the production ledger-Renta-expense source resolver; it is byte-identical today because the registry override layer (`resolve_region_category_profiles`) is deliberately empty (D2-C), and it activates with no further caller wiring once a territorial override is enrolled.
- New real-behavior tests (no mocks): `test_repository_wrapper_residence_ccaa_is_byte_identical_while_override_empty` proves a profile declaring `tax_residence.ccaa = madrid` yields casilla totals and observations byte-identical to the no-residence case; `test_repository_wrapper_threads_profile_residence_into_region_override_selection` injects a synthetic Canarias override and proves it is selected THROUGH the production wrapper when the profile declares Canarias (deductible halved) and falls through to state law for a Madrid profile -- the anti-dead-wiring proof that the profile-derived residence actually flows and is not silently dropped.
- Gates green: `test_renta_ledger.py` 26 passed (-n0, including the 24 pre-existing byte-identical baseline); `test_region_deductibility_selection.py` + `test_source_mesh_profile_live.py` 10 passed; `ruff check` and `ruff format --check` clean on both touched files. No registry change, so registry validation is untouched.

## Notes

- No registry, corpus, or figure change: the axis is a code wire over an empty override layer; nothing was fabricated. The territorial-regime figures remain unmodelled by deliberate ADR decision (RIC and Ceuta/Melilla reach the base through their own dedicated bindings / cuota deductions, not a SpendingCategory profile).
- Peer-WIP hygiene: the aggregation directory carried active uncommitted peer WIP in sibling modules (`_renta_gasto_ledger.py`, `_renta_income_ledger.py`, `_iva_ledger.py`, `_impatriado_income_ledger.py`); the S36 target `_renta_ledger.py` and its test were the only files edited, and the commit used an explicit pathspec with a verified zero-foreign staged set.
- Full-tree triage: a `-n auto` run of the aggregation test directory reported 57 failures, but all named failing files (source-mesh, retenciones, withholding, intracom, iva) passed cleanly on a sequential `-n0` re-run -- an xdist loader-cache race, not a regression, and none on the S36 surface. A concurrent peer `index.lock` briefly blocked staging; it was waited out (never force-removed) per shared-worktree safety.
