# Modelo 131 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 131 --year <YEAR> --period <PERIOD>` and treat that
output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value from this page — report the value the
CLI computes, with its `legal_refs`/`source_refs`.

## How Modelo 131 differs from Modelo 130

Modelo 130 (estimación directa) derives its rendimiento from the classified
ledger: ingresos minus gastos, computed by the engine. Modelo 131 (estimación
objetiva / módulos) is structurally different — the rendimiento neto is fixed
by the annual Orden de módulos (signos, índices y módulos tables published by
Hacienda for the taxpayer's IAE epígrafe), not by ledger totals. The taxpayer
(or their own módulos worksheet) supplies the rendimiento figure; the ledger
still matters for IVA and expense evidence on the same activity, but it does
not feed the IRPF instalment calculation the way it does on Modelo 130.

## The three activity blocks

Modelo 131 Section I splits by activity type, each with its own manual input
and its own computed pago-fraccionado-previo casilla:

- **Datos-base activities** (casillas `01`/`02`) — the common case for most
  módulos taxpayers (retail, hostelería, transporte, etc. under the
  personal-asalariado / consumo-de-energía datos-base scale).
  - `01` "Suma de rendimientos netos" — **manual input**. The datos-base
    rendimiento sum for the period, from the taxpayer's own módulos worksheet
    against the year's Orden de módulos. Not ledger-derived.
  - `02` "Pago fraccionado previo por datos-base" — **manual input** on most
    revisions. The RD 439/2007 art. 110.1.b objective-estimation scale (4 % / 3 %
    / 2 %, keyed on whether the activity has personal asalariado) applied to
    `01`; the 2 % scale minimum applies whenever `01` is positive, so `02` can
    never legitimately be zero on a positive `01` — see the ADVISORY guard
    below.
- **Sin-datos-base activities** (casillas `03`/`04`) — activities whose módulos
  scale is volumen de ventas o ingresos rather than the datos-base personal
  scale.
  - `03` "Volumen de ventas o ingresos sin datos-base" — manual input.
  - `04` "Pago fraccionado previo sin datos-base" — **computed** from `03` at
    the registry's fixed rate.
- **Agrarian activities** (casillas `05`/`06`) — actividades agrícolas,
  ganaderas y forestales.
  - `05` "Volumen de ingresos agrarios del trimestre" — manual input.
  - `06` "Pago fraccionado previo agrario" — **computed** from `05`.

## Total liquidación (common to all revisions)

- `07` "Suma de pagos fraccionados previos" — **computed**: `02 + 04 + 06`.
- `08` "Retenciones e ingresos a cuenta" — manual input, non-negative.
- `09` "Minoración por rendimientos netos de actividades económicas" — manual
  input.
- `10` "Diferencia" — **computed**. The cuota before the prior-quarter negative
  carry.
- `11` "Resultados negativos de trimestres anteriores" — **bound**, non-negative.
  Cross-quarter carry-forward, revision-stamped. The registry enforces a
  BLOCKING_RULE (`cap_le_when_positive(["11", "10"])`): when `10` is strictly
  positive, `11` must never exceed it. A verify BLOCKED here means the carried
  negative balance is overstated — do not override it.
- `12` "Pago de préstamos para vivienda habitual" — manual input (deducción por
  inversión en vivienda, transitional regime).
- `13` "Total" — **computed**.
- `14` "Resultado a ingresar de autoliquidaciones anteriores" — manual input
  (complementaria only).
- `15` "Resultado de la declaración" — **computed**. The amount to pay (a
  positive result) for the quarter — the final figure you report.

There is also an internal, non-exported computed casilla,
`saldo-negativo-fin-periodo` ("Saldo negativo trasladable a periodos
posteriores"), which the engine carries forward to feed casilla `11` on the
next quarter's revision.

## The flagship under-declaration risk

Because `01` (datos-base rendimiento) is a manual input with no engine behind
it on most revisions, a positive `01` with a zero `02` silently collapses the
whole datos-base contribution to `07`, and can silently zero the final result
`15` on real positive módulos activity. The registry closes this with an
ADVISORY predicate,
`modelo-131-<year>-pago-fraccionado-determinado-cuando-rendimientos-positivos`
(`implies_nonzero(["01", "02"])`): the RD 439/2007 art. 110.1.b scale minimum is
2 %, strictly greater than zero, so there is no legitimate positive-`01`/
zero-`02` case. Relay this ADVISORY to the taxpayer whenever it fires — never
treat it as noise, and never export past it without the taxpayer confirming the
figures (`no-silent-under-declaration`).

## Revision-year note: the 2025 módulos cross-check engine

The 2025 revision (only) additionally carries a units-times-coefficient
reference engine for a phased, incrementally-authored set of tabled IAE
activities (currently: peluquería 972.1, autotaxis 721.2, transporte de
mercancías 722, café-bar / restaurante 671.4/671.5/672.1-3/673.1/673.2, and
comercio al por menor de alimentación 642.1-4/642.5/642.6/643.1-2/644.1-3/
644.6/647.1/647.2-3): eight calculation-support casillas (`modulos-epigrafe`,
`modulos-1-unidades` through `modulos-7-unidades`) feed two internal computed
casillas (`modulos-rendimiento-neto-previo`, `modulos-rendimiento-neto-actividad`).
These are absent from the AEAT fichero-BOE layout (no `export_refs`) — they
exist purely to produce a reference figure that a further ADVISORY
(`modelo-131-2025-modulos-computed-diverges-de-c01`) compares against the
operator-declared `01`, prompting a review when they diverge by more than one
cent. This engine does NOT replace `01` as the filed value, and it is not
present on the 2026 revision — `aeat app modelo casillas 131 --year <YEAR>
--period <PERIOD>` tells you definitively whether a given filing year carries
it. Either way, `01` stays the manual, taxpayer-supplied figure you report.

## How to read it safely

- `01`, `03`, `05`, `08`, `09`, `12`, `14` are manual inputs supplied by the
  taxpayer (from their módulos worksheet, retenciones records, or prior
  autoliquidaciones) — never invent or estimate them.
- Computed casillas (`04`, `06`, `07`, `10`, `13`, `15`) come only from
  `aeat app modelo work calculate`. Reach them through the calculation, never by
  re-deriving the arithmetic.
- A positive `01` with a zero `02`, or positive rendimiento with a zero `15` and
  no declared reduction, is the under-declaration shape to question before any
  export (see `cadrumo-operator-grounding` and `cadrumo-operator-safety-handoff`).
- Cross-quarter carry (`11`, sourced from the prior quarter's
  `saldo-negativo-fin-periodo`) is revision-stamped; if a prior quarter's value
  cannot be confirmed, surface the advisory rather than trusting a silent zero.
