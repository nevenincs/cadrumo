---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S44'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Add registry source enrollment report for every committed modelo revision

## Scope

- `src/aeat/domain/calculations/registry/_queries.py`

## Description

- Add `RegistrySourceSite`, `RegistrySourceInventoryRow`, and `RegistrySourceInventoryReport` frozen pydantic models to `_queries.py`.
- Add `RegistryQueryService.source_inventory()`: walk every committed modelo revision, group its bindings by `BindingSourceKind`, and report per source kind the declaring `(modelo, revision_id)` sites with per-revision binding counts.
- Expose a `declared_source_kinds` property returning the frozenset of declared source kinds.
- Re-export the three report models on the registry package facade `__all__`.

## Outcome

- The report is genuinely new; `_queries.py` previously had no source-enrollment surface. It makes "which sources does the committed registry declare, and where" computable so the connectivity gates (S47/S48) can prove every declared source is routed or advised, never a silent blank (`no-dormant-source-resolvers`).
- Kept pure-domain: the report enumerates registry-declared source kinds only. The enrolled/deferred/reserved disposition overlay is a live-mesh (application) fact and is joined by the caller, honoring the `.importlinter` domain-not-application contract.
- Smoke-run over the live registry returns 20 declared source kinds (e.g. `ledger_iva_aggregation` 6 sites / 59 bindings, `manual_input` 12 sites / 783 bindings, `atribucion_member` 1 site / 4 bindings).
- Gates green: ruff check + format clean, ty clean on the module (a pre-existing bare-`list` annotation in the unrelated `_relation_inputs_by_target_binding` at HEAD is out of scope), collect-only clean.

## Notes

- The disposition axis (`BindingSourceDisposition`) lives in `application.aggregation`; domain cannot import it. Rather than duplicate the enum into domain or relocate it (net-new/ADR-scoped), the domain report stays disposition-free and the disposition join happens at the S47/S48 gates.
