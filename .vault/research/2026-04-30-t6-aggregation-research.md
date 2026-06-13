---
tags:
  - '#research'
  - '#t6-aggregation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-17-export-first-adr]]"
---

# `t6-aggregation` research: `period-close-to-casilla-inputs`

This research grounds the T6 aggregation implementation that turns Kent's classified transaction catalogue into formula-engine inputs for Modelo 130.

## Findings

`Engine.derive()` consumes `Mapping[str, Decimal]` in `src/aeat/domain/formulas/_engine.py`. It rejects non-Decimal values, rejects unknown casilla ids against the active `Ruleset`, and defaults missing non-computed casillas to `Decimal("0")`. Modelo 130 expects literal inputs including `01`, `02`, `05`, `06`, `08`, `10`, `13`, `15`, `16`, `18`; computed casillas include `03`, `04`, `07`, `09`, `11`, `12`, `14`, `17`, `19`. Modelo 303 has a much larger literal surface, with formulas using bases such as `01`, `04`, `07`, deductible inputs `29` through `43`, and result adjustments `65` and `67`.

`FilingInputsProviderProtocol` already exists in `src/aeat/application/workflow/_protocols.py` as `load_inputs(modelo, period, profile) -> Mapping[str, object]`. The workflow engine calls it immediately before draft build. A concrete financial provider can return Decimal values and still conform to the wider object-valued protocol.

`CategoryProfile.casilla_mappings` is a tuple of `CasillaMapping` values. Each mapping carries `modelo`, `period_type`, `casilla_code`, and a `CasillaMappingSign`. There is no mapping-level percentage. Deductibility percentage lives on `ProportionalityRule` (`fixed_pct`, `default_ratio`, statutory caps) and on transaction classification (`business_pct` for `MIXED`). Therefore aggregation must multiply the absolute transaction amount by the classification business ratio and the category proportionality factor where the proportionality rule is directly numeric. Statutory caps remain out of scope for exact enforcement because the transaction model does not carry enough per-day or per-person cap context.

Transactions are loaded through `TransactionCatalogueRepository`, which returns a frozen `TransactionCatalogue` from the encrypted FINANCIAL envelope. Period filtering can be an in-memory walk for this issue because the current repository exposes the catalogue aggregate rather than a queryable SQLAlchemy table. Dates are available as `raw.value_date or raw.booked_date`. The existing `FiscalPeriod` model supplies quarterly and annual inclusive `start` / `end` dates; monthly support is absent there, so T6 needs its own strict period model for `YYYY-Qn`, `YYYYQn`, `YYYY-MM`, and `YYYY`.

The post-#216 persistence path is the file-locked encrypted transaction envelope. The SQLAlchemy/Alembic substrate exists for broader storage work, but the transaction repository boundary for Kent's catalogue is still an aggregate load. `load_inputs` should therefore load the current catalogue via the repository and aggregate in memory.

Modelo 130 is the minimum viable scope and maps cleanly from business income and expense transactions into casillas `01` and `02`, then the formula engine derives the amount Kent owes (`04`, `07`, `19`). The current spending-category registry maps expenses to `01`, which conflicts with the Modelo 130 ruleset where `01` is income and `02` is deductible expenses. The T6 implementation must interpret transaction direction and mapping sign defensively and put outgoing deductible expenses into `02` for Modelo 130 unless a profile explicitly supplies a different non-conflicting mapping.

Modelo 303 can reuse the same ledger model and period filter, but correct VAT aggregation needs VAT base/rate split data that `Transaction` does not currently carry. The existing category registry's coarse IVA mapping to `71` is a result casilla, not a deductible input bucket, so including M303 would create misleading numbers. M303 should be accepted only when explicit mappings exist; otherwise the provider raises a typed unsupported/no-mapping error.

The Kent-readable provenance ledger needs at least the casilla id, subtotal, category id, and contributing transaction ids. Sorting transaction ids and provenance rows makes output deterministic and reviewable.
