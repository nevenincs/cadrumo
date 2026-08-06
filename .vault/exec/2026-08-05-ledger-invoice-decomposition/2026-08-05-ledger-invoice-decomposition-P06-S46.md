---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:14bcdb7cacfcff1ff9ebbd95ad689a8c76087f013dedff06ee5ba8d187f222de'
step_id: 'S46'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Wire the invoice decomposition contract to a consumer so its defect verdicts reach an operator, since it classifies nothing today and the aggregation paths each carry their own inline guard set instead

## Scope

- `src/cadrumo/application/aggregation`
- `src/cadrumo/application/invoices`

## Description

- Measure, before wiring, whether invoice coherence is the question each remaining consumer actually asks.
- Report a clean negative for the Modelo 369 OSS path and for the Modelo 347 branch, with the measurement that establishes it.
- Wire the contract to the Modelo 349 branch, narrowed to the defects where the record contradicts itself.
- Emit one excluded-but-visible advisory per disqualified record, naming the invoice and the contradiction.

## Outcome

Three consumers were examined and only one of them asks this question.

The OSS path is a clean negative, and the measurement is decisive: no `IvaCategory` member names an OSS operation at all. The OSS axis is the regime and the transaction kind, so an OSS invoice's IVA category is either absent or a Spanish-domestic value that does not describe the operation. Running the contract there would have returned every legitimate OSS invoice ungrounded. That path also already runs the coherence check that does apply to it, cross-checking the persisted cuota against the destination Member State's published rate — a sharper instrument for an OSS line than the Spanish category table.

The Modelo 347 branch is a clean negative too, confirming the earlier review. Its declared figure is the total contraprestación of operations with one third party, which the invoice's own totals identity already bounds and which no IVA category conditions; unconverted foreign records are withheld upstream. A category-driven exclusion there would drop real above-threshold operations out of an informativa on the strength of an unrelated missing field.

Modelo 349 is the one place the question belongs. Its clave is chosen FROM the declared category, and the base declared under it is the base imponible of an operation the record asserts is exenta under LIVA art. 25. A record claiming that exemption while carrying a repercuted cuota contradicts itself, and the contract cannot tell which of the two declarations is the mistake, so it grounds neither.

Wiring the whole contract there was wrong, and the suite caught it rather than reasoning doing so. Two ordinary intracomunitarias de servicios, created through the production service, dropped the declared operator count from two to zero. The root cause measured out as a taxonomy gap: the intra-community operation types for services map to no `IvaCategory` member at all, because the enum names goods, acquisitions and triangulation but not services. Treating an absent category as disqualifying therefore deletes an entire lawful operation class from the recapitulativa — a far larger under-declaration than the contradiction the check exists to catch.

The check is now scoped to the two defects where two declarations on one record disagree. Absence is not disqualifying. Exclusion is never silent: a missing intracomunitaria is an under-declaration however it went missing, so each disqualified record arrives named, with its contradiction and an action, and stays in the catalogue and editable.

## Verification

The wired check, both directions, on the real resolver with a real encrypted repository:

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_creation.py -q --no-header --tb=short -m integration
    15 passed in 11.26s

Regression sweep across the affected packages:

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/application/aggregation src/cadrumo/domain/invoices -q --no-header --tb=line -m "unit or integration"
    991 passed, 6 warnings in 274.02s (0:04:34)

Two mutations, each reverted after measuring:

- Check disabled, returning the contract to dormancy: 1 failed, 14 passed — the contradicting record is declared again.
- Check widened back to every defect: 1 failed, 14 passed — and the test that reddens is the intracomunitaria-de-servicios case, which is the regression this narrowing exists to prevent.

The second mutation is the load-bearing one. It demonstrates that the narrowing is not caution but a measured boundary: widening the check does not merely over-report, it silently deletes declarations.

## Notes

The probe that established the clean negatives ran the contract against invoices shaped as each consumer builds them, and is reproducible from the shapes described above; a domestic record with no declared category and an OSS-shaped record both came back ungrounded, while a coherent intra-community supply came back grounded and one carrying a cuota came back with the contradiction.

The expense path is deliberately absent from this Step. Its coherence check was added and reverted earlier on the grounding that deductibility runs through LIRPF art. 28 to the resultado contable, and nothing conditions a base's deductibility on a declared IVA category. That decision is not revisited.

Reported and not fixed here: the `IvaCategory` enum cannot express an intra-community supply or acquisition of SERVICES, so those operations reach Modelo 349 through `operation_type` alone and are structurally ungrounded to the decomposition contract. That gap is what forced the narrowing, and it will keep forcing narrowings until the taxonomy covers services.
