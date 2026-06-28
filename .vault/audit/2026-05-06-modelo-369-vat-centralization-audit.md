---
tags:
  - '#audit'
  - '#modelo-369-vat-centralization'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `modelo-369-vat-centralization` audit: `vat-iva-surface-and-modelo-369-readiness`

## Scope

This audit precedes any Modelo 369 OSS/IOSS registry work. The user flagged
that Modelo 369 is the first registry-grade modelo whose calculations and
bindings are derived directly from the ledger plus deductible-expense
surfaces and that interlinkage requires looping audits before code lands.

The audit catalogues every existing surface in the codebase that touches
VAT/IVA, EU Member State enumerations, rate definitions, classification
logic, and ledger ↔ modelo binding mechanics, and flags shadowing or
duplication risks before Modelo 369 design can begin. The audit does
not propose code changes; it produces the input for the Modelo 369
research and the centralization ADR.

## Findings

### A. The `aeat.domain.vat` substrate is mature and centralized

The package at `src/aeat/domain/vat/` already provides:

- **27-state EU enumeration** (`EUMemberState`) covering every current
  Member State as ISO-3166 alpha-2 lowercase identifiers.
- **15-member VAT category enumeration** (`VATCategory`) including
  `domestic_zero`, `domestic_exempt`, `domestic_not_subject`,
  `domestic_reverse_charge`, `intra_community_supply`,
  `intra_community_acquisition_reverse_charge`,
  `intra_community_triangulation`, `export_third_country_zero_rated`,
  `import_third_country`, `recargo_equivalencia`, `regimen_simplificado`,
  `operacion_no_sujeta`, `erroneous_invoice`, and `unknown`.
- **Closed `TransactionKind` taxonomy** with `goods`,
  `services_general`, `services_land_related`,
  `services_passenger_transport`, `services_restaurant`,
  `immovable_property`, `passenger_car`,
  `construction_reverse_charge`, `waste_reverse_charge`,
  `electronics_reverse_charge`, plus the OSS-aware
  `services_digital_b2c_oss`.
- **Residency / direction axes** (`IssuerResidency`,
  `CustomerResidency`, `CustomerTaxStatus`, `InvoiceDirection`) and a
  deterministic resolver (`classify_vat`) that emits
  `VATClassification` instances.
- **Period-keyed VAT catalogue** (`VAT_CATALOGUES_BY_YEAR`) and a
  load-time non-overlap-invariant rate table (`VAT_RATE_TABLE`) sourced
  from `registry/aeat/vat/rates.toml` (containing rates for ALL 27
  Member States including reduced/super-reduced/zero variants).
- **OSS-aware rule R14** (`R14_digital_b2c_oss`) inside the classifier
  that maps ES-issuer to EU-consumer B2C digital services through
  Article 70.Uno.4º LIVA via the OSS regime.

This is the right substrate for Modelo 369 destination-country VAT
breakdowns. The 27-state rate table is already in place and the
classifier already understands the basic OSS Union-scheme outbound
case for digital services.

### B. The VAT substrate is not yet wired into the registry

`grep` for any consumer of `aeat.domain.vat` symbols outside the package
itself returns only `src/aeat/core/config.py` (the catalogue root path
setting), `src/aeat/core/errors/registry/_domain.py` (the error-code
registrations), and `tests/import_contract/test_adr_layout_import_smoke.py`
(an import smoke test). No modelo TOML, no calculation-runtime module,
no ledger binding currently uses `classify_vat`, `lookup_rate`,
`VAT_RATE_TABLE`, or `VATCategory`.

This means Modelo 369 will be the first registry to stitch the VAT
substrate into the ledger ↔ modelo binding flow. The integration design
is therefore an architectural decision and not an implementation
detail; the ADR must record where the wiring belongs and which surfaces
become authoritative for OSS / IOSS calculations.

### C. IOSS and OSS regime taxonomies are not represented

`SERVICES_DIGITAL_B2C_OSS` is the only OSS-flavoured marker in the VAT
package. Modelo 369 declares three distinct schemes that the substrate
does not yet enumerate:

- **Esquema Unión** (OSS Union scheme): goods and services from an EU
  identification Member State to consumers in other EU Member States,
  filed quarterly.
- **Esquema de Importación** (IOSS): distance sales of imported goods
  with intrinsic value at or below 150 EUR shipped from outside the EU
  to EU consumers, filed monthly.
- **Esquema Exterior** (OSS non-Union scheme): services from non-EU
  taxable persons via an EU identification Member State, filed
  quarterly.

The classifier has no rules that distinguish the three schemes, no
enumeration of the schemes themselves, and no awareness of monthly vs
quarterly periodicity selection by scheme. None of these gaps are
fatal — Modelo 369 design can extend the substrate cleanly — but they
must be modelled before any 369 binding lands.

### D. Country validation in the invoice/transaction layer is shadow-prone

`src/aeat/domain/invoices/_validators.py` exposes `validate_country_code`
which accepts any ISO-3166 alpha-2 two-letter code without anchoring it
to `EUMemberState` or to a curated OSS-eligible-country list. Invoice
records therefore carry country strings that may or may not be EU
Member States, and Modelo 369 country-by-country breakdowns would need
runtime checks or a normalising adapter before the substrate's closed
enum can be applied.

The invoice layer also defines its own implicit "country" axis through
`payload["counterparty_country"]` without referencing the VAT
classifier's residency enums. This is a soft duplication: the same
real-world dimension (the counterparty's country) is represented as a
free-form string in the invoice surface and as a closed enum in the
VAT substrate, with no guarantee of consistency between them.

### E. No ledger-to-modelo VAT binding precedent exists

Modelos 303 / 390 (IVA autoliquidación trimestral and resumen anual)
are the canonical ledger-driven IVA modelos, but neither has a
committed registry TOML; only Modelo 349 (intra-community recapitulativa)
and Modelo 232 (operaciones vinculadas) carry IVA-adjacent registry
content, and both are informative-only, so neither demonstrates the
ledger → invoice → VAT classification → casilla aggregation flow that
Modelo 369 needs.

The calculation-truth-registry plan flags Modelo 303 and 390 as
heavy-legacy modelos pending teardown of duplicated formula rulesets,
filing builders, VAT/category mappings, and generated export modules.
Until 303/390 land their registry slices, Modelo 369 has no upstream
sibling to mirror; its architectural patterns will set the precedent
for the VAT-driven modelo registry shape.

### F. Rate-shadowing risk is bounded but real

`registry/aeat/vat/rates.toml` is the single committed rate table.
Sampling other repository surfaces for hardcoded rate literals (`21`,
`10`, `4`, `0.21`, `0.10`, `0.04` against VAT context) is not yet
exhaustive in this audit pass. The audit notes the risk and defers a
literal-sweep to the centralization ADR's pre-implementation gate.

### G. Member State enumerations live in the VAT module

Outside of `aeat.domain.vat`, references to `EUMemberState` or
equivalent enumerations appear only in tests and the calculation
registry's binding/export modules; no parallel Member State enum
exists elsewhere in the codebase. This is the cleanest dimension of
the audit and confirms that the centralization decision can rely on
`EUMemberState` as the single source of truth.

### H. Modelo 369's filing cadence is regime-conditional

Modelo 369 cadence is not a single value: IOSS declarations are
monthly, while Esquema Unión and Esquema Exterior are quarterly. The
existing modelo registry schema supports `monthly`, `quarterly`,
`annual`, `ad_hoc`, and `profile_based` cadences, but a single modelo
revision carries a single cadence. The Modelo 369 design must decide
whether to model the regime variation as separate revisions, separate
filing schedules under one cadence, or a profile-conditional cadence
selector.

## Recommendations

1. Treat Modelo 369 as the first registry-grade ledger-driven modelo
   and use it to set the precedent for the VAT-driven modelo binding
   shape. Do not foundation-only this slice; design ledger linkage,
   regime taxonomy, and per-country binding mechanics together.
2. Extend `aeat.domain.vat` (or a sibling module under
   `aeat.domain.vat.oss/`) with the three Esquema enumerations
   (`UNION_SCHEME`, `IMPORT_SCHEME`, `EXTERNAL_SCHEME`), the regime ↔
   periodicity mapping, and additional `TransactionKind` markers
   (goods OSS Union, IOSS distance sales, OSS external services) before
   the Modelo 369 registry TOML lands.
3. Capture the Modelo 369 BOE legal authority (Orden HAC/610/2021 and
   subsequent amendments) and the LIVA articles establishing the OSS
   regimes (Art. 163 sexiesvicies onwards) in a Modelo 369 research
   doc that accompanies this audit.
4. Decide via ADR whether the centralization gives rise to a new
   `aeat.domain.oss` module or extends `aeat.domain.vat` in place. The
   ADR must also decide whether per-destination VAT rate windows for
   OSS/IOSS calculations are declared in the existing
   `registry/aeat/vat/rates.toml` (already 27-state) or in a separate
   regime-scoped table.
5. Before the centralization ADR closes, run a literal-sweep audit
   across the codebase for hardcoded VAT rate values (`21`, `10`, `4`,
   `0.21`, etc. in VAT context) and confirm the rate table is the only
   authority. Any shadow rates surfaced must be referenced through
   `lookup_rate` after the ADR closes.
6. Do not start Modelo 369 registry TOML until: (a) Modelo 369
   research is complete, (b) the centralization ADR is accepted, (c)
   the substrate extensions for Esquema enumerations are in place, and
   (d) the ledger ↔ modelo binding mechanism for VAT-driven casillas
   is decided and recorded in the ADR. This loop discipline matches the
   user's directive that Modelo 369 design is conditional on looping
   audits, discovery, and research.
