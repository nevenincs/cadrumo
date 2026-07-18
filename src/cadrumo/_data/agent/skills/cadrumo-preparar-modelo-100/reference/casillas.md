# Modelo 100 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 100 --year <YEAR> --period 0A` and treat that output
as canonical; this page is orientation only, so you know which section a
casilla belongs to and where to look. Never report a casilla value from this
page - report the value the CLI computes, with its `legal_refs`/`source_refs`.
Because Modelo 100 spans thousands of casillas, always scope the read to the
section the taxpayer's question concerns rather than reading the whole set.

## The section map

Modelo 100 groups its casillas into sections that mirror the AEAT paper form.
The load-bearing groups an operator navigates:

- **Datos identificativos y personales** — contribuyente identification,
  marital status, descendientes and ascendientes, discapacidad. Profile-
  sourced; feeds the mínimo personal y familiar downstream.
- **Rendimientos del trabajo** — salary and pension income and its
  deducciones. Typically profile- or manually-entered (a payslip or
  certificado de retenciones), not ledger-derived, unless the taxpayer's
  ledger separately tracks it.
- **Rendimientos del capital inmobiliario** — rental income from properties
  not affected to an actividad económica. Manually entered per property;
  distinct from any business-use property already covered by the ledger.
- **Rendimientos del capital mobiliario** — interest, dividends, and similar.
  Manually entered from the taxpayer's financial statements.
- **Rendimientos de actividades económicas** — estimación directa or
  estimación objetiva net result. This is the one section that is
  ledger-derived the way Modelo 130/131 are, for a taxpayer who carries on a
  business or professional activity. It also folds in each quarter's Modelo
  130/131 pago fraccionado as a pago a cuenta.
- **Ganancias y pérdidas patrimoniales** — capital gains and losses.
  Manually entered per transaction (transmisión).
- **Base imponible / base liquidable** — the general and del ahorro bases,
  computed by the engine from every income section above plus reducciones
  (aportaciones a planes de pensiones, pensiones compensatorias, and
  compensación of prior years' negative bases).
- **Mínimo personal y familiar** — computed from the personal/family data,
  split between the tramo estatal and the tramo autonómico of the taxpayer's
  comunidad autónoma of residence.
- **Cuota íntegra / cuota líquida / cuota resultante** — the escala-driven
  tax computation (estatal and autonómica), deducciones estatales, and
  deducciones autonómicas (which vary by comunidad autónoma - read the
  applicable set from the calculated revision, never assume one comunidad's
  deducciones apply to another).
- **Pagos a cuenta** — retenciones suffered (from Modelo 111/115/123/180/190
  cross-modelo relations) and pagos fraccionados (from the year's Modelo
  130/131 quarters), subtracted from the cuota líquida to reach the cuota
  diferencial.
- **Resultado de la declaración** — the final amount to pay or to be
  refunded.

## How to read it safely

- Inputs fall into three provenance classes and each is fixed differently:
  ledger-derived (actividades económicas - fix the ledger and re-calculate),
  profile-sourced (personal/family data, comunidad autónoma - fix the
  profile), and manually-entered with no ledger counterpart (capital
  inmobiliario/mobiliario, ganancias patrimoniales, most deducciones - route
  to the role that owns operator-entered facts). Never edit a casilla to a
  number you prefer regardless of provenance.
- Computed casillas (every base, mínimo, cuota, and the resultado) come only
  from `aeat app modelo work calculate`. Reach them through the calculation,
  never by re-deriving the escala arithmetic.
- A strictly positive base liquidable general with a zero cuota resultante de
  la autoliquidación and no declared minimo-personal-y-familiar or deducción
  explanation is the under-declaration shape to question before any export
  (see `cadrumo-operator-grounding` and `cadrumo-operator-safety-handoff`). It is legitimate
  for a filer whose base sits at or below the mínimo, so confirm rather than
  assume either way.
- The Modelo 130/131 pagos-fraccionados fold-in and the retenciones
  cross-modelo relations are revision-stamped; if a source quarter or a
  source modelo's value cannot be confirmed, surface the advisory rather than
  trusting a silent zero pago a cuenta.
- Deducciones autonómicas differ by comunidad autónoma of residence. Read the
  set the registry actually resolved for the taxpayer's declared comunidad
  from the calculated revision rather than naming a deducción from memory.
