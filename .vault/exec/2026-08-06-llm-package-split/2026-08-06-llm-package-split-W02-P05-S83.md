---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d91fad6c37a475f02c8e0531bdfdf558304690162484495515a6469791656e04'
step_id: 'S83'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Prove an invoice confirmed from a structured document grounds through the decomposition contract rather than refusing as undeclared, red if the renta sales-evidence path still refuses it with an ungrounded-decomposition verdict

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Resolve the domestic IVA category from the rate the document states and its issue date, when the document's own category code carries no special treatment.
- Compose the two shipped primitives rather than writing a third: date-aware tier resolution, then tier-to-category.
- Decline rather than approximate on multi-rate, on a recargo-bearing supply, and on an unregistered or ambiguous rate.
- Prove the confirmed invoice grounds through the decomposition contract, with the declining branches exercised.

## Outcome

A standard-rated structured document states UNTDID `S`, which means "no special treatment" -- the rate itself carries the meaning. The parser therefore yielded no category, and the record was minted with none. That failed the decomposition contract, and the renta sales-evidence path then counted the row's BANK CASH instead of its ingresos integros, dropping the base, the cuota AND the retencion.

The refusal was never an exclusion. The row still contributed; it contributed the wrong figure. That is what made it quiet.

Resolution now comes from `rate_kinds_for_declared_rate` composed with `domestic_categories_by_rate_kind`, both already shipped and both grounded -- the rate records carry their own legal_refs. No new mapping was written: the second primitive's docstring records that three independent copies existed before it was promoted, so a fourth would have been the exact duplication this campaign exists to remove.

Three cases decline, and declining is visible rather than silent: the record stays undeclared, the decomposition reports it, and the renta path raises an advisory.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_grounds_for_renta.py -m "unit or integration" -n 0
    3 passed in 26.30s

Mutation-checked at the coordinator boundary rather than accepted on the green.
Forcing the resolver to always decline:

    AssertionError: an invoice read from a structured document must be legally interpretable
    AssertionError: assert <InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED...
    2 failed, 1 passed in 30.76s

So the tests guard the resolution, not the fixture. Confirmed the fixture IS the
standard-rated case the step names: `TaxTypeCode 01`, `TaxRate 21.00`, and the
parser yields `iva_category: None` for it.

## Notes

Two things worth carrying forward.

**The blocker was mis-scoped before it was measured.** The sweep first concluded this Step could not be closed by a test at all, on the reasoning that RD-ley 4/2024 made a percentage identify a tier only in combination with a date, so inverting the tier-to-rate mapping would be an invention barred by `aeat-safety-legal-gates`. The refusal was right; the stated hazard was not. Measured against the shipped table, no percentage maps to two tiers -- 2 % and 4 % both resolve to SUPER_REDUCED. RDL 4/2024 broke tier-to-rate, not rate-to-tier. The date still matters, but for a different reason than the one given.

What actually unblocked it was finding that the date-aware resolver already ships. A symbol-name search for an inversion of the tier mapping finds nothing; the concept is filed under `rate_kinds_for_declared_rate`. That is the RAG mandate earning its place rather than illustrating it.

**The recargo exclusion is the sharpest of the three declines.** A recargo-bearing supply resolves its rate cleanly, so a naive implementation would categorise it. But the decomposition contract grounds such a supply under BOTH `DOMESTIC_GENERAL` and `RECARGO_EQUIVALENCIA`, so a wrong pick would be caught nowhere downstream. A guess that no gate can refuse is worse than a decline that every surface reports.

The multi-rate decline is not a limitation of this resolution; it is the open modelling decision. `Invoice.iva_category` is single-valued and a two-tier document has two answers. That half remains an ADR.
