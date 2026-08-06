---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:4c383ba28319bcdc6c7863f1021cd15423d66b81d22e4b322488240640e0b6b2'
step_id: 'S07'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Stop synthesising exactly one line at BOTH synthesis sites, the canonical builder and the live bulk importer, accepting a supplied line set and proving a two-line invoice at different rates persists and aggregates per line with no persisted-schema change

## Scope

- `src/cadrumo/application/invoices/_creation.py`

## Description

- Located every production line-synthesis site before editing, which refuted the Step's central premise.
- Added an optional line-set parameter to the canonical builder and threaded it through the persisting service.
- Made a taxable base that disagrees with the summed line subtotals refuse rather than resolve.
- Added the mixed-rate persistence proof, the disagreement refusal, and a positive control for the single-rate path.
- Corrected the module docstring that asserted the import path had its own synthesis.

## Outcome

**A canonically-written invoice can now carry several IVA rates.** Omitting the line set keeps the single-line synthesis every existing caller relies on, so the change is additive.

Why it matters beyond expressiveness: collapsing a mixed-rate invoice to one line reports the correct GRAND TOTAL while attributing the entire cuota to a single rate. The per-rate breakdown is exactly what the IVA modelos declare, so the error is invisible in the figure an operator would eyeball and wrong in the figure that is filed.

With a line set supplied the caller states the base twice, once as the summed subtotals and once as the taxable base. A disagreement **refuses**. Silently preferring either would let the caller believe the other was recorded, and on this field that means declaring a base the operator never entered.

**The Step's central premise is refuted, and it was load-bearing.** `S07` is written against "BOTH synthesis sites", and its verification criterion is emphatic: the Step "is not complete with one site fixed" because "the live bulk importer carries its own single-line synthesis".

It does not. There is exactly ONE production line-synthesis site. The bulk importer routes every row through the canonical builder, and its own row-model docstring says its fields synthesise the line "exactly as `build_catalogue_invoice` does" — by delegating to it. Fixing the one site fixes both transports at once.

That instruction would have sent an executor hunting for a second site that does not exist. The likelier failure is worse than wasted effort: an executor who trusts the criterion and cannot find the second synthesis may conclude the importer needs one, and add a parallel implementation to satisfy the plan — manufacturing exactly the duplication this campaign exists to remove.

**The residual limit the premise was groping at is real but different.** The bulk import ROW model admits one rate per row, so the CSV format cannot express a mixed-rate invoice even now that the builder can hold one. That is a limit of the file format, not a second synthesis to keep in step, and it is recorded rather than fixed here because widening the import row format is a different decision with its own operator-facing consequences.

## Verification

    uv run --no-sync pytest .../test_creation.py .../test_bulk_import.py -m integration -n 0 -q --no-header
    34 passed in 14.14s

    uv run --no-sync ruff check .../\_creation.py .../test_creation.py
    All checks passed!

The mixed-rate proof persists through the real encrypted repository and reloads, rather than asserting on the in-memory model, because the claim is that the per-rate breakdown SURVIVES the boundary and not merely that the builder assembled it.

The single-site claim was measured, not inferred from the delegation call alone: a sweep for line-set construction across all production modules returns one site.

## Notes

**A peer's uncommitted edit blocked the wide regression run and was left alone.** Midway through this Step the invoice test packages began failing collection with a `StopIteration` raised at import time from a module-level lookup in `application/aggregation/_modelo_bindings.py`, which expects a length constraint on a diagnostic field that no longer carries one.

That file is dirty against `HEAD` — live peer work in flight, not a committed break, and not caused by this Step, which touches neither module. Earlier runs in this same session over the same packages passed, so it landed while this Step was in progress. It was neither reverted nor "fixed": an uncommitted change with no reachable owner is live peer work.

The Step is verified through the two test modules that do not import the affected chain, which is a narrower gate than intended. The full invoice-package regression should be re-run once that peer edit settles, and this record names the exact failure signature so a later reader can tell it apart from anything this campaign owns.

A marker note, repeated from an earlier Step because it recurred: running these modules by path alone deselects every test. Both runs above carry the integration marker.
