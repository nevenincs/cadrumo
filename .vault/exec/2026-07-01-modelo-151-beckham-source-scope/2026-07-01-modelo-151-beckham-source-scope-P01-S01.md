---
tags:
  - '#exec'
  - '#modelo-151-beckham-source-scope'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S01'
related:
  - "[[2026-07-01-modelo-151-beckham-source-scope-plan]]"
---

# Add ledger_impatriado_income_aggregation source kind, ES-source classifier, M151 base binding, mesh resolver + enrollment, and non-tautological tests (ES folds in, foreign segregated, None fails loud, trabajo admitted)

## Scope

- `src/aeat/core/aggregation.py`
- `src/aeat/application/aggregation/_impatriado_income_ledger.py`
- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/_data/registry/aeat/modelos/151`

## Description

- Add `LEDGER_IMPATRIADO_INCOME_AGGREGATION` to the canonical `BindingSourceKind` StrEnum in `core/aggregation.py` and derive it into the `LEDGER_BINDING_SOURCE_KINDS` frozenset (now six ledger members).
- Author the impatriado income classifier `_impatriado_income_ledger.py`: an annual ledger aggregation admitting an INCOMING row into `impatriado.base-liquidable-general` only when `source_jurisdiction` resolves to `ES`, admitting trabajo income (the class M130 excludes), and emitting a typed `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue carrying the rejected jurisdiction code for a foreign row and a null code for an unresolved (`None`) row.
- Fail loud on `source_jurisdiction is None`: an unresolved jurisdiction is segregated, never coerced to `ES` (the load-bearing no-silent-under-declaration safeguard).
- Add the registry binding family in `_ledger_bindings.py` (selector model, raise-style and list-style validators, resolver, unsupported-observation screen); register it in the `_bindings.py` selector and validator dispatch tables and re-export through the registry package facade.
- Add the `LedgerImpatriadoIncomeAggregationSourceResolver` mesh resolver, enroll it in `merge_source_resolutions` and the `_ENROLLED_SOURCE_KINDS` / `BUCKET_AGGREGATION_LOCK_SOURCES` policy sets.
- Declare the M151 base binding TOML (`0001-m151-impatriado-base.toml`, grounded on `ley-35-2006:art-93`) and flip `impatriado.base-liquidable-general` from `input_kind = "manual"` to `bound`.
- Update the ledger-frozenset parity gate (five to six members), the resolver-enrollment pin (fourteen to fifteen), and add the M151 aggregation test module.

## Outcome

Implemented ADR Option A Phase 1 and Phase 2. The compelled `source_jurisdiction` axis is now consumed to compute the Modelo 151 impatriado Spanish-source base, with per-row audit-visible segregation of foreign and unresolved income. Focused tests pass (7 M151 aggregation tests plus the taxonomy, mesh-parity, and resolver-enrollment gates); `pytest --collect-only -q src/aeat` collects clean; ruff and pyright are clean on the changed surface. Phase 3 (the savings escala, art. 93.2.e.2 / art. 25.1.f TRLIRNR) is deferred corpus-first per the ADR and tracked as `P02.S02`.

## Notes

- The full registry authority load and two full-authority tests (`test_source_mesh_profile_live.py`) are red in this shared worktree from an unrelated Modelo 100 peer campaign (Madrid nacimiento/adopción profile bindings committed in `8ea7ef3a7` after the profile-live test was last currentized, plus uncommitted M100 construct/formula WIP). Confirmed red at HEAD and owner-triaged as peer churn: M151 is validated in isolation via `load_modelo_directory` and the M151 modelo compiles and validates cleanly.
- The parity-gate test file carried unrelated comment-only peer WIP; the own change was landed via a HEAD-anchored temp-index apply-cached drive so the peer WIP was preserved.
- No locale leaf was scaffolded for the new issue reason: aggregation issue reasons are free-text `detail` strings in this codebase (the M130 `TRABAJO_INCOME` precedent), not localized keys.
