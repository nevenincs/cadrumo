---
tags:
  - '#research'
  - '#convenio-doble-imposicion'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:c65b27fa75150df6b52b2a37740796a5d156a639188f499a24d77aba8fe6b76b'
related:
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
  - '[[2026-05-27-non-resident-irnr-axis-adr]]'
  - '[[2026-06-30-m210-categorical-conditional-predicate-adr]]'
  - '[[2026-06-30-convenio-doble-imposicion-adr]]'
---

# `convenio-doble-imposicion` research: `Convenio doble imposicion treaty-rate framework`

Scope: issue #537 (P1, parent of a treaty tranche -- child #558 Spain-Argentina, sibling
#557 already-modelled art-25.1.b pension rates). The issue title reads "Convenio doble
imposicion not modelled", but a treaty-rate-override mechanism **already exists** and is
live on the M210 calculate path. The decision-relevant question is therefore not "build
from scratch" but "generalise, deepen, and type the axis of the existing M210-local
mechanism into a reusable framework, and reconcile a second out-of-sync treaty surface".
Everything below is grounded against the code at HEAD plus the bundled BOE corpus; no
treaty rate was invented (rule `aeat-safety-legal-gates`).

## Findings

### F1 -- A working treaty-rate override already ships, but it is M210-named and M210-local

The override is fully wired on the M210 calculate path, not a stub:

- **Parameter table** `m210-convenio-rates`
  (`modelos/210/revisions/2025/parameters/0002-m210-convenio-rates.toml`),
  `data_type = "convenio_rate_table"`, three seed rows: `GB/general -> 0.24`,
  `MA/interest -> 0.10`, `AR/pension -> DOMESTIC_TARIFF`.
- **Typed row schema** `ConvenioRateRow` (`registry/_schema_formula.py:182`): `country_code`
  (2-char ISO 3166-1 alpha-2, `^[A-Z]{2}$`), `tipo_renta` (free `str`, max 64), `rate`
  (parseable `Decimal` string OR literal `"DOMESTIC_TARIFF"`), `legal_ref_anchor`,
  `legal_refs`, `valid_from`/`valid_to`. The parameter validator forbids mixing
  `convenio_rates` with `bracket_table`/`keyed_bracket_table` and requires row uniqueness.
- **Runtime op** `m210_resolve_rate` (`registry/_formula_runtime.py:625`), dispatched from
  formula `m210-tipo-gravamen-2025-resolve`. It reads `tipo_renta` (text casilla), the
  TRLIRNR baseline keyed-bracket table, the convenio table, the art-25.1.b pension tariff,
  and the profile-bound `country_of_fiscal_residence` binding, then returns the resolved
  `Decimal`. **Replacement semantics, not stacking**: when the residence country has a row
  for the filed `tipo_renta`, the treaty rate *replaces* the domestic baseline.
- **Missing-row safety**: a profile-declared treaty country with no row for the requested
  `tipo_renta` yields `_M210_CONVENIO_MISSING_SENTINEL`, rewritten by the application-layer
  verification sweep into a BLOCKING finding (governing ADR `2026-05-27-m210-irnr-full-engine`
  D2.4). This honours `no-silent-under-declaration`.

Every identifier on this path is `m210_*`-prefixed and physically located under
`modelos/210/`. **There is exactly one consumer** -- M210 is the only IRNR modelo in the
registry (no M216/M211/M213/M226). The framework concern in #537 is real but currently
single-consumer; the cost of the M210-local shape is latent and surfaces the moment a
withholding modelo (M216 retenciones a no residentes -- dividends/interest/royalties) needs
the same treaty data.

### F2 -- The income-type axis (`tipo_renta`) is an untyped free-text casilla

`tipo_renta` is `data_type = "text"`, `semantic_role = "irnr_tipo_renta"`, `input_kind =
"manual"` (`modelos/210/revisions/2025/casillas/0001-casillas.toml:23`). Its value set is
closed in practice -- `general`, `ue_residente`, `pension`, `interest`,
`ganancia_patrimonial`, `inmobiliaria` -- but enforced nowhere as an enum. The same free
string keys the baseline table, the convenio table, and the pension branch. This violates
the closed-value-set mandate (`aeat-architecture-boundaries`: closed axes are `StrEnum` in
`core/`, CLI emits `Choice([...])`); grep of `src/aeat/core/` finds no `TipoRenta` enum.
The today-dated peer ADR `2026-06-30-m210-categorical-conditional-predicate` had to build a
categorical-equality verification predicate precisely because the numeric `implies_nonzero`
operator cannot read the text `tipo_renta` -- direct evidence the untyped axis is already
costing adjacent campaigns.

### F3 -- A second, out-of-sync treaty surface is a Python literal in a feature module

`TaxpayerProfile.convenio_aplicable` (`domain/deadlines/_models.py:725`) derives a BOE
treaty reference from `country_of_fiscal_residence` via a hand-maintained
`_CONVENIO_BY_COUNTRY: dict[str, str]` literal (`_models.py:840`) covering six countries:
`GB, DE, FR, US, NL, MA`. This is informational/advisory only (it labels which treaty
applies; it carries no rate). It is **out of sync with the calc authority**: the rate table
covers `GB, MA, AR` -- Argentina (the #558 child, the only one with a non-trivial
`DOMESTIC_TARIFF` allocation row) is absent from the informational map, while `DE/FR/US/NL`
are labelled treaty countries that resolve to *no* override (silent fall-through to the
domestic baseline). Two regulatory surfaces, two coverage sets, drifting -- the
inlined-literal failure mode `aeat-schema-central-config` forbids.

### F4 -- Treaty legal grounding already follows the registry pattern; three treaties grounded

Treaty articles live in `registry/aeat/legal/irnr.toml` as first-class legal entries with
`corpus_ref` into the bundled consolidated corpus: `convenio-es-gb-2013:art-6`
(immovable-property income), `convenio-es-ma-1978:art-11` (interest, source-state tax capped
at 10%), `convenio-es-ar-1992:art-19` (public-function pensions, Spain-side allocation). Each
carries `document_id`, `required_text`, `notes`, and points at
`corpus/normatives/html/convenio-es-*-art-*.html`. This is exactly the shape
`registry-calculation-legal-grounding` and `legal-grounding-verifies-bundled-authoritative-corpus`
mandate, and the template any new treaty must follow. The grounding is agent-prepared and
needs the honest `reviewed_by`/operator-re-stamp posture (filing-grade rates).

### F5 -- A subtle legal-semantics gap: "ceiling" vs "flat replacement"

Spanish CDIs phrase source-state taxation as a **ceiling**, not a flat rate: the
Spain-Morocco art-11 corpus reads "the tax cannot exceed 10 per cent of the gross amount".
Modelling that as a flat `0.10` replacement is correct today **only because 10% < the 19%
domestic art-25.1.f baseline** -- the "mas favorable" outcome and the ceiling outcome
coincide. `ConvenioRateRow.rate` cannot distinguish a *flat* treaty rate, a *ceiling*
(apply `min(domestic, treaty)`), an *allocation* (`DOMESTIC_TARIFF`), or an *exemption*
(source state may not tax). The framework should make the override kind typed data so "mas
favorable" / limitation-of-benefits is computable rather than coincidental.

### F6 -- Profile selection axis is already present and correct

`country_of_fiscal_residence` (ISO alpha-2) and `fiscal_residency`
(`FiscalResidency.NON_RESIDENT_IRNR`) exist on `TaxpayerProfile`
(`domain/deadlines/_models.py:512`), validated (NON_RESIDENT_IRNR must declare a country,
TRLIRNR art-2), with derived `ue_eee_status`. The convenio op already binds
`country_of_fiscal_residence` as its selection key. **No new residence axis is needed**; the
open questions are only how an income *item* is tagged with its treaty-relevant type (F2)
and whether the redundant `convenio_doble_imposicion_country` field (referenced in the
governing ADR prose) should be retired in favour of the single residence fact.

### F7 -- Out-of-scope surfaces the issue names; the framework only needs to leave room

The issue mentions PE (permanent-establishment) thresholds, employment income, and
withholding-modelo treatment (dividends/interest/royalties). None is modelled today: M210 is
the "sin establecimiento permanente" autoliquidacion, and there is no withholding modelo.
The framework must not foreclose them (a treaty file should be able to hold PE thresholds and
per-income-type rates the day M216 lands) but should not model them in the first slice.

### Constraints carried from existing decisions

- `aeat-registry-authority-flow`: any treaty data is TOML -> loader/compiler -> strict schema
  -> authority -> snapshot; a new authoring surface needs a loader path and cache-fingerprint
  inclusion.
- `calculation-source-canonical-mechanism` / `one-aggregation-path-pull-equals-calculate`: the
  treaty override is ONE rate-resolution path; do not fork a parallel rate mechanism.
  Generalising `m210_resolve_rate` (sole consumer) is behaviour-preserving and permitted by
  `no-legacy-compatibility` (delete the old name, no shim).
- `aeat-safety-legal-gates` + `legal-grounding-verifies-bundled-authoritative-corpus`: every
  treaty rate grounded against the bundled consolidated CDI corpus and cross-checked against
  live BOE/AEAT; advisory/calc only, never live filing.

### Peer-WIP note (re-read HEAD before action)

`domain/deadlines/_models.py` and
`modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml` are
**uncommitted-modified** in the shared working tree (today-dated
`m210-categorical-conditional-predicate` campaign, 68 insertions). The peer diff does not
touch the convenio/`tipo_renta`/`country_of_fiscal` lines, but `_models.py` holds
`_CONVENIO_BY_COUNTRY` and the convenio profile properties -- so the F3 relocation
recommendation lands in a file under active peer edit and the eventual plan MUST use the
apply-cached gated discipline (`uncommitted-wip-is-not-orphaned`), not a blind edit.

### What was not investigated (bounded honesty)

- The full Convenios Espana bibliography (~90 active treaties) was not enumerated; only the
  three seeded plus six informational-map countries were read. The first-slice country
  recommendation rests on the informational map already naming DE/FR/US/NL.
- The M216 withholding surface does not exist, so the cross-modelo consumption claim is a
  design projection, not an observed second consumer.
- The interaction of treaty rates with the art-24.6 UE/EEE expense-deduction base path was
  not traced end-to-end; the override acts on the rate, not the base, so it is believed
  orthogonal but not proven here.
