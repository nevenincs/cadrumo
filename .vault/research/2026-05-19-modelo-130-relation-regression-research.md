---
tags:
  - '#research'
  - '#modelo-130-relation-regression'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
---

# `modelo-130-relation-regression` research: `Modelo 130 same-year negative-result carry-forward`

This research records the non-IVA regression discovered while verifying the
previous-period relation runtime used by the Modelo 303 IVA compensation chain.
Modelo 130 is not an IVA filing, but it exercises the same class of same-model,
prior-period relation: a current-period calculation consumes a previous-period
filing result.

## Findings

Modelo 130 has a legally distinct carry-forward pattern for negative quarterly
results. AEAT's Modelo 130 instructions state that casilla `15` records, only
when casilla `14` is positive, the unsigned amount of negative results obtained
in casilla `19` of any prior Modelo 130 autoliquidacion from the same exercise
that have not already been deducted. The amount in casilla `15` cannot exceed
the positive amount in casilla `14`.

The same instructions state that casilla `19` is the result after subtracting
casilla `18` from casilla `17`, and if the result is negative, that negative
result can be deducted in later instalment payments of the same year when a
positive amount permits it. This makes Modelo 130 a same-year pool of unused
negative results, not a simple previous-quarter copy.

The current registry contains the relation
`modelo-130-rel-self-prior-quarter-negative`, targeting binding
`modelo-130-resultados-negativos-anteriores` and sourcing
`saldo-negativo-fin-periodo`. That relation is structurally related to the IVA
fix because both depend on the registry runtime's ability to resolve
same-model previous-period evidence into a target binding. It differs in legal
semantics because Modelo 130 may consume any prior same-year negative result
not yet deducted, subject to the positive casilla `14` cap.

The prior IVA verification pass found Modelo 130 failures in the broader
cross-dependency suite:

- The same-model previous-period relation contract failed for
  `modelo-130-rel-self-prior-quarter-negative`.
- Formula-bearing revision relation consumption did not accept the Modelo 130
  relation as implemented.
- Edge-year observation aggregation failed because the relation expected a
  previous observation in a situation where the period requirements were not
  aligned with the target period.

Re-running the wider cross-dependency suite on 2026-05-19 also exposed a
separate registry-loading blocker: `_brackets_overlap_in_same_window` is
referenced by `_schema.py` but not defined. That blocker masks the full
cross-model failure set until fixed. It should be treated as a prerequisite
verification repair, not as the Modelo 130 legal rule itself.

## Source Notes

Official sources checked:

- AEAT Modelo 130 instructions:
  `https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html`
- AEAT Modelo 130 procedure page:
  `https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/pagos-fraccionados/gestiones-pagos-fraccionados.html`
- BOE consolidated IRPF Regulation, Real Decreto 439/2007, article 110:
  `https://boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20231228&tn=0`

## Recommendation

Create a dedicated Modelo 130 remediation wave linked to the IVA compensation
chain work because it validates the same relation-runtime abstraction after the
IVA `source_output` offset fix. The implementation must not blindly reuse the
IVA previous-quarter wallet model. It must model Modelo 130's own rule: prior
same-year negative casilla `19` amounts that remain undeducted, capped by the
current positive casilla `14`.
