---
tags:
  - '#research'
  - '#iva-compensation-chain'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# `iva-compensation-chain` research: Modelo 303/390 IVA compensation-chain grounding audit

This audit checked whether the AEAT implementation models the legally relevant
IVA compensation balance carried between periodic Modelo 303 filings and
reconciled in Modelo 390.

## Findings

The legally grounded framing is: when deductible input VAT (`cuotas deducibles
soportadas`) exceeds output VAT accrued/recharged (`cuotas devengadas` /
`repercutidas`) in a VAT settlement period, the excess is a `saldo a compensar`.
Under LIVA article 99.5, that excess may be compensated in later VAT
returns within the statutory four-year window. When refund is available, the
taxpayer may opt for refund instead; once refund is chosen for that balance,
the same balance is no longer available for compensation in later returns.
LIVA article 115 separately governs the general year-end refund route for
subjects who could not make deductions effective through the article 99
compensation mechanism.

AEAT Modelo 303 instructions for 2025 expose this as a three-casilla balance
surface:

- Casilla 110: `Cuotas a compensar pendientes de periodos anteriores`.
- Casilla 78: `Cuotas a compensar de periodos anteriores aplicadas en este periodo`.
- Casilla 87: `Cuotas a compensar de periodos previos pendientes para periodos posteriores`.

The 2025 instructions also state that if the taxpayer opts to compensate prior
period balances, the maximum possible amount is applied, capped by the sum of
casillas 66 and 77. If casilla 78 is filled, the result cannot be filed as
`A COMPENSAR`.

Modelo 390 instructions expose annual reconciliation via casilla 662 for
compensation balances generated in the year but not included in casilla 97 of
the annual summary, i.e. balances not transferred through the final-period
autoliquidacion.

Implementation audit observations:

- `src/aeat/_data/registry/aeat/modelos/303.toml` still maps
  `iva.compensacion-anteriores` to number `67`, not the current 2025 110/78/87
  balance surface.
- The 303 registry comments describe an automatic prior-quarter chain, but the
  binding `modelo-303-compensacion-anteriores` declares only `source_output`.
  The direct previous-filing resolver skips bindings without `source_casillas`,
  so it resolves no binding value for this casilla.
- The relation `modelo-303-rel-self-compensacion-anteriores` declares
  `period_alignment = { mode = "previous_quarter" }` and
  `source_periods = ["1T", "2T", "3T"]`, but the resolver only uses
  `source_period_offset_from_target`. For a 2T filing it therefore requires
  all three source periods with copy aggregation instead of just 1T.
- The application calculation path can map binding values into bound casilla
  inputs when those binding values exist, so the regression is in
  previous-filing/relation resolution and registry semantics, not in bound input
  materialisation.

Confirmed local resolver behaviour:

- For Modelo 303 year 2026 period 2T with a prior 1T observation containing
  `iva.compensacion-disponible-fin-periodo = 200.00`,
  `resolve_previous_filing_binding_values` returns `{}`.
- `relation_source_requirements` asks for periods `("1T", "2T", "3T")`.
- `resolve_relation_values_from_observations` fails because 2T and 3T are not
  present, even though 2T should only need the immediately previous quarter.

Risk:

This is a critical tax-calculation regression if Modelo 303 is expected to
produce filing-grade IVA results. It can overstate payable IVA when a
compensation balance exists, fail to preserve the AEAT-managed compensation
wallet semantics, and produce Modelo 390 reconciliation gaps around casillas
97/662. It also carries legal-grounding drift because LIVA article 99.5 is
implemented as a simple prior-quarter negative-result carry rather than the
current Modelo 303 110/78/87 application/pending balance mechanism.

Recommended remediation:

- Replace the old casilla 67 abstraction with a grounded 110/78/87 model for
  supported 2025+ 303 surfaces, keeping explicit revision handling for older
  layouts if needed.
- Model `saldo pendiente`, `saldo aplicado`, and `saldo pendiente posterior`
  as distinct observations with legal_refs/source_refs.
- Use an offset-based previous-period relation for the immediately prior filing
  or implement a dedicated IVA compensation-wallet resolver that can account for
  balances carried from older years, refund choices, and maximum-application
  rules.
- Add non-tautological tests based on AEAT 303/390 published examples:
  110=1200 and 66+77=1000 implies 78=1000 and 87=200; 110=200 and
  66+77=1000 implies 78=200; Modelo 390 casilla 662 examples should reconcile
  balances generated but not included in casilla 97.
