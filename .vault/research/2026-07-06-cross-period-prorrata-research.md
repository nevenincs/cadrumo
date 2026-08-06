---
tags:
  - '#research'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:3f964e9a4fb7fdc84fcf2b27fe56138b4b144062677a9ec4eaf9b67d281beb2b'
related: []
---

# `cross-period-prorrata` research: `provisional carry and settlement regularisation grounding`

## Findings

### Decision input

The silent-zero-base campaign formally deferred its Modelo 303 prorrata volume
rows because a current-period `base_amount_sum` binding would compute the wrong
legal percentage for mixed traders. The deferred follow-up named a cross-period
prorrata mechanism: prior-year definitive percentage applied provisionally
across the year, then a final-period regularisation against annual volumes.

The IVA complexity scope research reached the same conclusion from LIVA arts.
102-106: the prorrata substrate already computes the general/especial/sectoral
figures, but the annual regularisation is not wired into the calculate mesh.
It identified the gap as an ADR-grade cross-period carry and settlement problem,
not a bounded registry mirror.

### Accepted decision shape

The accepted cross-period-prorrata ADR chooses a per-ejercicio prorrata register
as the carry home. It is seeded from the stamped prior settlement observation in
the normal art. 105.Uno case and also records art. 105.Dos AEAT-authorised and
art. 105.Tres inicio-de-actividades provisional percentages with provenance.

The ADR also decides that in-year apportionment must occur in the shared IVA
ledger aggregation path, reducing deducible cuotas rather than bases. At
settlement, declared annual volume casillas remain the authority for the
definitive percentage, with a ledger rollup serving as a reconciliation advisory
until all art. 104.Tres exclusions can be classified.

### Current plan state

The L3 cross-period-prorrata plan translates that decision into six waves and
forty steps. Its first wave builds the register foundation; later waves seed the
carry, apply in-year apportionment, feed regularisation, promote the deferred
source kind only after an AEAT manual oracle proof, and close the prior
silent-zero-base deferred rows honestly.

At the time this bridge was written, `vaultspec-core vault plan status
2026-07-06-cross-period-prorrata-plan --json` reported 0 of 40 steps complete
and `W01.P01.S01` as the next open step. That first step already has active
non-authored work in `src/aeat/core/__init__.py` and
`src/aeat/core/_prorrata_register.py`, so this research bridge does not claim
or close it.

### Implementation guardrails

Future execution should preserve the ADR's boundaries:

- Do not fabricate a provisional percentage. The in-force value must come from
  the stamped prior definitive observation, an AEAT-authorised override, or an
  inicio-de-actividades recorded value.
- Do not apply prorrata to bases. The ADR requires cuota apportionment while
  bases remain full.
- Do not promote `PRORRATA_REGULARIZACION` before the end-to-end AEAT manual
  oracle proof lands.
- Treat the existing peer WIP in the register-enum surface as owned by its
  author until it is committed or explicitly released.

### Sources

- `2026-07-05-cross-period-prorrata-adr`: accepted cross-period prorrata
  decision.
- `2026-07-06-cross-period-prorrata-plan`: L3 implementation plan and current
  40-step execution ledger.
- `2026-06-19-silent-zero-base-aggregation-adr`: original correctness deferral
  for per-period prorrata volume bindings.
- `2026-06-19-silent-zero-base-aggregation-W01-P02-S03` and
  `2026-06-19-silent-zero-base-aggregation-W01-P02-S04`: formal deferral records
  naming the cross-period prorrata follow-up.
- `2026-07-01-iva-complexity-hardening-scope-research`: prorrata gap inventory
  and legal-shape research.
- `src/aeat/domain/iva/_prorrata.py`: existing computation substrate consumed by
  the ADR.
- `src/aeat/application/aggregation/_iva_ledger.py`: current shared IVA ledger
  aggregation path where in-year cuota apportionment must eventually land.
