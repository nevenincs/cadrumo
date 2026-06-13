---
tags:
  - '#research'
  - '#modelo-369-vat-centralization'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-modelo-369-vat-centralization-audit]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `modelo-369-vat-centralization` research: `oss-ioss-regime-and-ledger-binding-shape`

This research consolidates the legal and technical requirements that
Modelo 369 places on the registry, the centralized VAT substrate, and
the ledger ↔ modelo binding flow. It is the input for the
centralization ADR. It does not propose code changes; it captures the
authoritative requirements that the ADR must answer.

## Modelo 369 legal authority

The modelo is created by Orden HAC/610/2021, de 16 de junio (BOE
identifier `BOE-A-2021-10161`), titled "Impuesto sobre el Valor
Añadido. Autoliquidación de los regímenes especiales aplicables a los
sujetos pasivos que presten servicios a personas que no tengan la
condición de sujetos pasivos, que efectúen ventas a distancia de
bienes y ciertas entregas interiores de bienes."

Article 1 of the order approves the model. Article 2 enumerates the
obligados across the regimes and ties each regime to its declaration
period. Article 3 sets the plazo as "dentro del mes natural siguiente
al del final del período al que se refiera la autoliquidación" — the
calendar month following the close of the period.

The substantive legal basis is the LIVA (Ley 37/1992) regimes
established by Articles 163 sexiesvicies through 163 octiesvicies (the
nine articles introduced by Ley 11/2020 transposing EU Directive
2017/2455 and aligned with EU Council Implementing Regulation
282/2011). Modelo 369 implements the autoliquidation surface for
these LIVA regimes; the registry must cite the LIVA articles as the
substantive obligation source and the order as the form authority.

## Three regimes (Esquemas)

Article 2 of HAC/610/2021 enumerates three regimes:

- **Esquema Exterior** (régimen especial aplicable a los servicios
  prestados por sujetos pasivos no establecidos en la Comunidad).
  Period: each natural calendar quarter. Identification Member State:
  Spain when the non-EU taxable person elects ES as the identification
  Member State for OSS purposes.
- **Esquema Unión** (régimen especial aplicable a las ventas
  intracomunitarias a distancia de bienes, a las entregas de bienes
  dentro de un Estado miembro efectuadas a través de interfaces
  electrónicas que faciliten dichas entregas, y a los servicios
  prestados por sujetos pasivos establecidos en la Comunidad pero no
  en el Estado miembro de consumo). Period: each natural calendar
  quarter. Identification Member State: Spain when the EU taxable
  person is established in Spain (or has its main place of business in
  Spain) and elects ES as the identification Member State.
- **Esquema de Importación** (régimen especial aplicable a las ventas
  a distancia de bienes importados procedentes de territorios terceros
  o países terceros). Period: each natural calendar month. The
  identification Member State is Spain when the taxable person elects
  ES, with or without an intermediario depending on residency.

The three regimes share the modelo identifier (369) but carry
different periodicity, different obligados, and different content
sections. The model document includes per-Member-State-of-consumption
breakdown rows: each line carries a destination Member State, the
applicable VAT type tier (general / reduced / zero), the taxable base
in EUR, the VAT amount in EUR, and (for corrections) a reference to
the original autoliquidation being amended.

## Cadence is regime-conditional

Modelo 369 cannot be modelled as a single-cadence registry revision.
The three regimes split:

- Esquema Exterior → quarterly (1T / 2T / 3T / 4T).
- Esquema Unión → quarterly (1T / 2T / 3T / 4T).
- Esquema de Importación (IOSS) → monthly (12 declarations per year).

The registry schema currently allows one cadence per modelo
revision. Modelo 369 design must either declare separate revisions
per regime (each carrying its own period selector and filing
schedule), use a profile-conditional cadence selector, or treat the
modelo as `ad_hoc` with multiple filing schedules under one
revision. The ADR must record the chosen approach so the deadline
window generation, period selector validation, and live-discovery
sweeps stay coherent.

## Centralized VAT substrate readiness

The audit confirmed that `aeat.domain.vat` already provides the
27-state Member State enumeration, a 27-state rate table with
effective windows, and a deterministic classifier with one OSS-aware
rule. The substrate is therefore the right home for Modelo 369's
destination-country VAT lookups.

What the substrate does not yet model:

- A closed enumeration of the three Esquemas (Exterior / Unión /
  Importación) plus their periodicities.
- IOSS-specific transaction kinds: distance sales of imported goods
  with intrinsic value at or below 150 EUR, electronic-interface
  facilitator deliveries, services provided by non-EU taxable persons
  through the External regime.
- A regime ↔ classifier rule set for Modelo 369 declarations: the
  classifier currently routes ES outbound digital B2C through OSS
  (rule R14) but does not enumerate other Esquema Unión cases, IOSS
  cases, or Esquema Exterior cases.
- A correction-mechanism representation: Modelo 369 supports
  amending earlier declarations by referencing the original
  autoliquidation; the substrate has no current model for amendment
  references.

These gaps are extensions, not redesigns. The substrate's frozen
Pydantic schema and load-time non-overlap invariants generalise
cleanly to the new regime taxonomy.

## Ledger ↔ modelo binding gap

Modelo 369 derives its casillas from the ledger: each line in the
modelo aggregates trading transactions classified into a regime,
broken down by destination Member State and rate tier. The audit
established that no committed modelo registry currently consumes the
VAT substrate, so the binding mechanism is undefined.

Three concrete questions the centralization ADR must answer:

- Should Modelo 369 bindings reference the VAT substrate via
  `selector.classification` keys (e.g., regime + Member State + rate
  tier), or via dedicated registry binding sources such as
  `oss_aggregation` that the runtime resolves through the substrate?
- How does the runtime aggregate filtered ledger lines into casilla
  values? The existing `aeat.domain.calculations.registry._bindings`
  module supports `previous_filing` and `manual_input` source kinds;
  Modelo 369 needs a new ledger-aggregation source, distinct from
  invoice-level bindings.
- How are deductible expenses tracked when the regime requires it?
  IOSS allows certain VAT recovery via the registration Member State;
  Esquema Exterior does not allow deduction in the autoliquidation;
  Esquema Unión follows local-Member-State rules. The substrate must
  expose a deductibility predicate per regime to keep filing-grade
  values out of Python.

The ADR must answer these before any Modelo 369 binding lands. The
plan's existing rebuild-plan directive ("no formula or binding lives
in Python; everything is registry-backed") applies; the open
question is the *shape* of the new binding source, not whether to
use the registry.

## Required corpus artefacts before any registry slice

Pre-implementation, the registry must hold:

- The Orden HAC/610/2021 BOE HTML and per-article excerpts for at
  minimum Articles 1 (aprobación), 2 (obligados / período), and 3
  (plazo).
- The relevant LIVA Article 163 sexiesvicies–octiesvicies excerpts
  (LIVA = Ley 37/1992, BOE-A-1992-28740) for the three regime
  authorities. The classifier must cite these articles for the rule
  set additions.
- Any subsequent BOE amendments to HAC/610/2021 (none catalogued in
  this research pass; the corpus retrieval should sweep BOE for
  modifying Orders before the ADR closes).
- The official AEAT record-design artefact for Modelo 369. The
  manifest at
  `corpus/aeat_official/disenos_registro/modelo_369/manifest.json`
  records what AEAT publishes; the registry workbook parity refs
  must point at one of the listed artefacts.

## Loop discipline

Per the user directive, this research and the audit document the
known surfaces and known gaps but do not exhaust the problem. The
centralization ADR is the next step; if the ADR review surfaces
further unknowns, this research must be re-run before the ADR
closes. No Modelo 369 registry TOML lands until: (a) this research
and the audit are reviewed, (b) the ADR is accepted, (c) the
substrate extensions are in place, and (d) the ledger ↔ modelo
binding mechanism is decided.
