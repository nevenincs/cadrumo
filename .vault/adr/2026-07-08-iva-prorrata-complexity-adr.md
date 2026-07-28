---
tags:
  - '#adr'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-28'
related:
  - '[[2026-07-08-iva-prorrata-complexity-audit]]'
  - '[[2026-07-07-prorrata-especial-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-research]]'
  - '[[2026-07-06-cross-period-prorrata-research]]'
---


# `iva-prorrata-complexity` adr: `art-103.Dos.2 mandatory-especial advisory emit audience` | (**status:** `accepted`)

## Problem Statement

The LIVA art. 103.Dos.2 +10% mandatory-especial advisory
(`build_prorrata_especial_mandatory_advisory`,
`src/cadrumo/application/calculations/_prorrata_regularizacion.py`, W02.P03.S13) is
built and unit-tested but never emitted on the live Modelo 303 settlement path —
a dormant advisory. The 2026-07-08 campaign audit found the live emit is not a
wiring step because of two blockers. First, the comparison needs the ejercicio's
whole-year deducible cuota total under BOTH regimes, and the live collector
(`collect_prorrata_regularizacion_diagnostics`,
`src/cadrumo/application/modelo/_prorrata_regularizacion_advisory.py`) holds only
the declared regime's per-period `casilla_values`. Second — the audience
problem this ADR decides — the obligation targets a filer computing under
GENERAL prorrata, but a general-regime bucket carries no per-input
`input_classification` (declaring one is itself the especial-election workflow,
S14/S24), so the especial-regime total is genuinely not derivable for the
intended audience without the operator first classifying. A naive emit could
only fire confirmatorily for an already-especial bucket, inverting the
obligation's purpose.

The statutory text, verbatim from the bundled consolidated LIVA
(`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html`, `#a103`, redaction
Ley 28/2014 in force 01/01/2015): "Dos. La regla de prorrata especial será
aplicable en los siguientes supuestos: 1.º Cuando los sujetos pasivos opten por
la aplicación de dicha regla en los plazos y forma que se determinen
reglamentariamente. 2.º Cuando el montante total de las cuotas deducibles en un
año natural por aplicación de la regla de prorrata general exceda en un 10 por
ciento o más del que resultaría por aplicación de la regla de prorrata
especial." The comparison is annual ("en un año natural") and its especial side
is defined by the art. 106 per-input use classification — a taxpayer-asserted
fact the umbrella `prorrata-especial` ADR already ruled is operator-supplied,
never derived.

## Considerations

- The two shadow directions are NOT symmetric. The general-regime total is
  mechanically derivable for any bucket: art. 104 applies one whole-entity
  percentage (already resolved by the register as the apportionment's
  `percentage`, which for an ESPECIAL entry is the same art. 104.Dos common
  percentage) to every deducible cuota — no taxpayer-asserted fact is missing.
  The especial-regime total requires each input's art. 106 use classification —
  a taxpayer-asserted fact. So the especial-to-general shadow is always honest;
  the general-to-especial shadow is honest ONLY when every deducible soportado
  row in the ejercicio carries a declared `input_classification`.
- A defaulted classification is an invented regulated input. The umbrella ADR's
  constraint is explicit: there is no default classification — an unclassified
  deducible input surfaces an advisory, never a silent assumed use. A shadow
  especial total built on defaults would put a fabricated figure inside a
  legal-obligation claim.
- `no-silent-under-declaration`: when the obligation check cannot run for its
  intended audience, saying so (and naming the enabling action) is the mandated
  posture; silence is not.
- The general filer CAN be served honestly: rows in a general bucket may carry
  `input_classification` (the S24 flag is accepted there, currently advised as
  inert). A fully classified general bucket makes the especial shadow a
  computation over operator-declared facts — the check then genuinely nudges
  the general filer the law targets.
- Channel: live calculate-path advisories are `CalculationSourceDiagnostic`
  rows from the collector fan-out
  (`collect_bucket_aggregation_advisory_diagnostics`), projected at the CLI
  into warning-severity Notices with code
  `modelo.work.calculate.source_advisory` and `reason`/`source_kind` on
  `Notice.context` (`_modelo_work_calculate_cli.py`). Every sibling prorrata
  advisory (missing-provisional, casilla-44, bienes-inversión) rides this one
  channel (`cli-notices-are-the-only-diagnostic-channel`).
- The whole-year totals cannot come from per-period `casilla_values`; they need
  an annual-window ledger aggregation. One observation aggregation
  (`aggregate_iva_ledger_observations_from_repositories` over the ejercicio's
  annual period, canonical `Period` grammar per
  `period-filter-single-boundary-authority`) can feed TWO
  `resolve_iva_ledger_binding_values` passes (a general-stamped vs an
  especial-stamped `IvaLedgerProrrataApportionment`) through the SAME canonical
  resolver — `one-aggregation-path-pull-equals-calculate` is preserved; there
  is no second aggregation implementation.

## Considered options

- **(A) PROMPT-TO-CLASSIFY, extended with an honest-computability check branch
  (CHOSEN).** At settlement (4T/0A), when prorrata applies and the especial
  total is not honestly derivable (a general bucket with any unclassified
  deducible soportado row), emit a non-blocking advisory that the art-103.Dos.2
  obligation may apply and that verifying it requires classifying inputs —
  computing NO especial shadow. Whenever both totals ARE honestly computable
  (an especial bucket always, via the mechanical general shadow; a general
  bucket whose deducible soportado rows are all classified), run the real +10%
  check and surface the S13 advisory verbatim. Pro: serves the intended
  general-filer audience without fabrication, names the enabling action, and
  un-dormants the S13 builder on every honestly-checkable bucket. Con: the
  typical unclassified general filer gets a conditional prompt, not a computed
  verdict — that is the honest maximum.
- (B) ESPECIAL-SHADOW COMPUTATION via default/heuristic classification
  (REJECTED). Pro: a computed verdict for every general filer. Con: fatal — a
  defaulted art. 106 classification is a fabricated regulated input inside a
  legal-obligation claim; it contradicts the umbrella ADR's no-default
  constraint and `aeat-safety-legal-gates` (never invent legal behaviour), and
  would train operators on false verdicts in both directions.
- (C) CONFIRMATORY-ONLY emit for already-especial buckets (REJECTED as the
  scope; subsumed as one branch of A). Pro: trivially honest; the general
  shadow needs no missing facts. Con: fatal as the whole answer — the
  obligation exists to move general filers into especial; an emit that can
  never reach a general filer inverts the advisory's purpose and leaves the
  intended audience silent (`no-silent-under-declaration`).

## Constraints

- Parent stability: the S13 builder + `is_especial_mandatory` (accepted
  substrate, `PRORRATA_ESPECIAL_MANDATORY_MULTIPLE = 1.10`), the regime-aware
  apportionment (`_apply_especial_apportionment`, landed W02), the W04 operator
  ingress (`app ledger prorrata elect-especial`, `--input-classification`,
  landed), and the settlement collector are all landed and consumed, not
  re-opened. The S13 builder's comparison and message are surfaced verbatim,
  never re-implemented (`composition-service-no-parallel-write-path`).
- No fabricated figures: the prompt branch carries NO amounts; the check branch
  carries only totals computed from operator-declared facts through the
  canonical resolver.
- The threshold semantics stay the builder's, and the substrate owns that
  boundary reading — this ADR consumes it and does not re-open it. AMENDED: the
  boundary reading this constraint recorded, strictly-greater-than with exactly
  the margin treated as silent, has since been corrected in the substrate and no
  longer describes HEAD. The parenthetical note that the statute reads "exceda en
  un 10 por ciento o mas" was the live divergence, and it is closed: reaching the
  margin now suffices, and the margin itself is resolved from the filing year
  because the provision has two redactions across the served window. The ruling
  and its alternatives are in `2026-07-07-prorrata-especial-adr` decision D4,
  grounded by `2026-07-27-conformance-cli-P02-S58`. Nothing in this record's own
  decision changes: the emit-audience ruling consumes whatever boundary the
  substrate owns, and the pinned boundary tests referenced above were corrected
  with the substrate rather than preserved.
- Sectorized registers (LIVA arts. 9.1.c/101) are a NAMED DEFERRAL: the
  art-103.Dos.2 comparison composes per sector (each sector carries its own
  regime and percentage), and v1 of this emit scopes to the whole-entity
  (non-sectorized) register only. A sectorized bucket gets neither branch in
  v1; the deferral is recorded here and in the implementation's docstring, not
  silently.
- Advisory-noise budget: both branches fire only at the settlement periods
  (`4T`/`0A`), matching the sibling regularización branch — once per ejercicio,
  never per quarter. The prompt branch additionally requires a resolved
  apportionment; when the provisional ladder is unresolved the existing
  missing-carry advisory is the one actionable signal.

## Implementation

S21 implements exactly this; the coordinator builds it as scoped here.

**New aggregation helper (the plumbing ruling).** The dual-regime totals ARE
needed — but only on the check branch, and as one aggregation plus two
apportionment passes, not two aggregations. A public helper in
`src/cadrumo/application/aggregation/` (exported through the package `__all__`
per `service-imports-via-top-level-reexports`), e.g.
`compute_annual_deducible_totals_by_regime(bucket_id=..., ejercicio=...,
revision=...)`, that: builds the ejercicio's annual window via the canonical
`Period` grammar; calls `aggregate_iva_ledger_observations_from_repositories`
once; resolves `resolve_iva_ledger_binding_values` twice over the same
observations — once with a GENERAL-stamped and once with an ESPECIAL-stamped
`IvaLedgerProrrataApportionment` (both carrying the register's resolved
percentage) — summing the deducible-cuota binding ids; and returns a small
frozen model carrying `deduction_under_general`, `deduction_under_especial`,
the count of unclassified deducible soportado observations, and the register
regime. It returns `None` when no apportionment resolves or the register is
sectorized (the named deferral). The classification-completeness signal is
computed over the annual window's soportado observations that contribute to
deducible cuota bindings.

**Collector branch.** `collect_prorrata_regularizacion_diagnostics` gains a
final settlement-only branch (guarded by the existing
`_SETTLEMENT_PERIOD_TOKENS` and applicability derivation): call the helper; if
`None`, silent. If the especial total is honest (regime ESPECIAL, or regime
GENERAL with zero unclassified deducible soportado rows), call
`build_prorrata_especial_mandatory_advisory` with the two totals; a `None`
return is silence, a `Notice` is adapted into one `CalculationSourceDiagnostic`
whose `message` is the builder's message verbatim, with `reason =
"prorrata_especial_obligatoria"` and `source_kind =
"prorrata_especial_mandatory"`. Otherwise (regime GENERAL, unclassified rows
present — the intended-audience prompt), emit one diagnostic with `reason =
"prorrata_especial_check_unavailable"`, the same `source_kind`, and this
message (inline Spanish, like every sibling collector message; no new `tr()`
key on this surface): "La prorrata especial puede ser obligatoria para
{ejercicio} (LIVA art. 103.Dos.2.º: se aplica cuando las cuotas deducibles por
prorrata general exceden en un 10 por ciento o más de las que resultarían por
la regla especial). La comprobación requiere clasificar el uso de cada cuota
soportada (art. 106): declare '--input-classification' en las operaciones del
ejercicio y, en su caso, ejecute 'app ledger prorrata elect-especial
--ejercicio {ejercicio}'. Quedan {n} operaciones sin clasificar."

**Typed reason axis.** Two new members on the
`CalculationSourceDiagnosticReason` Literal in
`src/cadrumo/application/aggregation/_source_mesh.py`:
`"prorrata_especial_obligatoria"` and
`"prorrata_especial_check_unavailable"`.

**Envelope surface.** No CLI change: both diagnostics ride the existing
projection and surface as warning-severity Notices with code
`modelo.work.calculate.source_advisory` (and the wizard's
`modelo.work.wizard.source_advisory`), with the distinguishing `reason` and
`source_kind` on `Notice.context`. The S13 builder's own Notice code
(`modelo.work.calculate.prorrata_especial_obligatoria`) and its pinned unit
tests are unchanged; the builder remains the single comparison/message owner.

**S24 inert-notice touch-up (the one locale change).** The existing
`cli.ledger.add.input_classification_inert` message states the flag is inert
without an especial election; after S21 the classification also enables the
settlement art-103.Dos.2 check for a general bucket, so that message is updated
to say so. This IS a `tr()` locale change: it MUST be made via `python -m
cadrumo.locales set` for all four catalogues (en/es/ca/hu), never by hand-editing
the `.yml` files, and `test_parity` plus the translation-honesty gate must stay
green (`aeat-locales-cli`; a locale gap already bit this campaign).

**Files changed:** `src/cadrumo/application/aggregation/_iva_ledger.py` (or a new
sibling module) plus `src/cadrumo/application/aggregation/__init__.py` (helper +
export), `src/cadrumo/application/aggregation/_source_mesh.py` (reason members),
`src/cadrumo/application/modelo/_prorrata_regularizacion_advisory.py` (branch),
`src/cadrumo/entrypoints/cli/_ledger.py` locale-key default text plus
`src/cadrumo/locales/{en,es,ca,hu}.yml` via the locales CLI, plus tests. No
registry TOML change, no new CLI verb, no new Notice code.

**Anti-dormant test shape** (in
`src/cadrumo/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
or a sibling module; real repositories via `isolated_runtime_profile`,
law-derived scenarios per the S15 oracle pattern — spreads derived from the
art. 106 reglas, never from the substrate under test):

- FIRES on the intended audience: a GENERAL-regime bucket whose deducible
  soportado rows ALL carry declared classifications, constructed so the general
  total exceeds the especial total by more than 10% → at `4T` the collector
  emits the `prorrata_especial_obligatoria` diagnostic carrying both totals.
- FIRES confirmatorily: an ESPECIAL-elected bucket with the same law-derived
  spread → the same diagnostic (the general shadow is mechanical).
- PROMPT fires: a GENERAL bucket with sin-derecho volumes, a resolved
  apportionment, and at least one unclassified deducible soportado row → the
  `prorrata_especial_check_unavailable` diagnostic naming
  `--input-classification` and `elect-especial`, carrying no amounts.
- SILENT otherwise: a mid-year period (`1T`); no sin-derecho operations
  (prorrata inapplicable); a fully-classified general bucket with the spread at
  or below +10%; an especial bucket at or below +10%; a sectorized register
  (the named deferral).
- LIVE-PATH integration (the anti-dormant essence): at least one fires case is
  asserted through `collect_bucket_aggregation_advisory_diagnostics` — the
  actual calculate fan-out — not only through the collector called directly.

## Rationale

Option A is the only direction that serves the statute's audience without
inventing its facts. The decisive observation is the shadow asymmetry: art. 104
makes the general total a mechanical function of facts the register already
holds, while art. 106 makes the especial total a function of taxpayer-asserted
use classifications. The check therefore runs exactly where the law's own
inputs exist — always for an especial bucket, and for a general bucket
precisely when the operator has supplied the classifications the comparison is
defined over — and everywhere else the app says, once per ejercicio at
settlement, that the obligation may apply and names the one action that enables
the check. B fabricates a regulated input; C abandons the audience. The
plumbing follows from A: the prompt branch computes nothing, and the check
branch needs one annual observation aggregation with two apportionment passes
through the one canonical resolver — the minimal true form of the audit's
"dual-regime re-aggregation".

## Consequences

- Gain: the S13 advisory is un-dormanted on every honestly-checkable bucket,
  and the art-103.Dos.2 obligation now reaches its intended general-filer
  audience as an actionable, non-fabricated prompt.
- Gain: classification acquires a second consumer for general buckets (the
  settlement check), turning the S24 "inert" framing into a truthful "enables
  the obligation check" — surfaced via the updated locale message.
- Cost accepted: an unclassified general filer receives a conditional prompt,
  not a verdict; the verdict is gated on operator work (classifying the
  ejercicio's inputs). This is the honest ceiling.
- Cost accepted: the check branch adds one annual ledger aggregation plus two
  apportionment passes at settlement calculates for prorrata buckets.
- Deferral: sectorized registers are out of the v1 check/prompt scope; the
  per-sector composition of the art-103.Dos.2 comparison is follow-up work.
- Pitfall: a future agent must not "complete" the prompt branch by defaulting
  unclassified rows to COMMON to force the check — that reintroduces option B.
  The especial apportionment's common-default exists for the elected especial
  regime's own filing, not for manufacturing the obligation comparison on a
  general bucket.
- Pitfall: do not move the emit to mid-year periods for earlier warning; the
  statutory comparison is annual, and a partial-year spread is not the
  art-103.Dos.2 figure.
