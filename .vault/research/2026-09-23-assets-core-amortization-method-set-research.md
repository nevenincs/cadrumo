---
tags:
  - '#research'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:bdd427d46da7de0ece20d21dfc871804fe98de73ecf8d00a086c301c96cd5597'
related:
  - "[[2026-09-21-assets-core-lifecycle-and-integration-research]]"
---




# `assets-core` research: `IRPF activity amortization method set for 2025`

The 2025 activity-asset engine enrols only the linear table and the EUR 300
free-depreciation election. This record establishes which further methods the
common-regime direct-estimation modalities permit for tax year 2025, the
arithmetic each method prescribes, and which conditions depend on facts the
product does not hold. All legal text below was read from the bundled BOE and
AEAT corpus, not from memory.

## Findings

### Regime scope: normal applies every LIS method, simplified restricts material assets to the linear table

LIRPF art. 28.1 determines activity net income by Impuesto sobre Sociedades
rules (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html#a28`). RIRPF
art. 30.1a requires the simplified modality to amortize inmovilizado material
linearly from the simplified table (Orden 27-3-1998) and applies the ERD rules
to those amounts (`rd-439-2007.html#a30`). The restriction names material
assets only. Whether the LIS art. 12.1.b/c methods may apply to intangible
assets in either modality is not stated after LIS art. 12.2 was redrafted
with effect from 2016; the AEAT 2025 manual (part 1, p. 456) says every
intangible is a definite-life asset amortized over its useful life.

### Linear table: any coefficient between the maximum and the one implied by the maximum period

RIS art. 4.1 (`rd-634-2015.html#a4`) accepts the maximum coefficient, the
coefficient derived from the maximum period, or any coefficient between them.
The period tables already exist beside the coefficient tables in
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
but the resolver in
`src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py:73` reads
only the maximum coefficient. RIS art. 4.2 adds a multi-shift coefficient
(minimum plus the max-min difference times hours/8). RIS art. 4.3 allows up to
twice the maximum coefficient on the price of a used asset; buildings under ten
years old are not used assets. The amortizable base excludes residual value
and land (RIS art. 3.2).

### Constant percentage: normal regime, weighted coefficient on the pending value

LIS art. 12.1.b and RIS art. 5 apply a constant percentage to the pending
value. The percentage is the elected linear coefficient weighted by 1.5
(period under 5 years), 2 (5 to under 8) or 2.5 (8 or more), never below 11%.
The period is the one corresponding to the elected coefficient, and the
amount pending in the period in which the useful life ends is amortized in
that period. Buildings, mobiliario and enseres are excluded (RIS art. 5.2).
Used assets are admitted (RIS art. 5.3). The AEAT manual repeats these rules
(part 1, pp. 454-455).

### Sum of digits: normal regime, period chosen between the table bounds

RIS art. 6 assigns digits to the years of the amortization period, highest
first or in reverse order. The period is any value between the maximum period
and the one implied by the maximum coefficient, inclusive. The quota per digit
is the acquisition price divided by the digit sum. Because digits number whole
years, the admissible periods are the integers inside that closed interval.
Buildings, mobiliario and enseres are excluded (RIS art. 6.2). The manual
repeats this (p. 455).

### Approved plan: an administrative act fixes the distribution

RIS art. 7 lets the taxpayer propose a plan whose temporal distribution the
AEAT approves, amends with consent, or approves by silence after three months
(art. 7.6-7.7). An approved plan takes effect in periods ending after its
submission unless it states otherwise (art. 7.8). The engine can validate an
approved distribution against the base but cannot create the approval.

### Justified amount: permitted, but not validatable from registry facts

LIS art. 12.1.e accepts an amount the taxpayer justifies. The justification is
evidence of actual depreciation outside any tabled authority.
`2026-08-23-amortization-casilla-mapping-adr` requires every scheduled asset
to validate its coefficient and useful life, and it refuses caller-provided
amounts.

### Intangibles: useful life, or a one-twentieth ceiling

LIS art. 12.2 amortizes intangibles over their useful life. When that life
cannot be estimated reliably, and for goodwill, the annual deduction is capped
at one twentieth. The 5% parameters are already authored in the 2025 file but
are unused. The manual explains that the accounting charge (10%) and the tax
ceiling (5%) diverge (p. 456).

### ERD acceleration: twice the maximum linear coefficient for new assets

LIS art. 103.1 lets new material assets, real-estate investments and
intangibles made available in an ERD period use twice the maximum table
coefficient. LIS art. 101 defines ERD as prior-period net turnover below EUR 10
million. The manual applies this in both modalities and gives a worked
example: EUR 36,000 x 24% x 1/12 = EUR 720 (p. 472). For indefinite-life
intangibles and goodwill, the manual applies 150% to the art. 12.2 amount
(p. 471). The bundled consolidated LIS art. 103.5 instead cross-refers to
"apartado 3 del artículo 13", which described the pre-2016 regime. The two
official sources therefore disagree on the provision's current scope.

### Free depreciation incentives

LIS art. 12.3.b/c make R&D-affected material and intangible elements
(excluding buildings) freely amortizable, and allow R&D buildings linearly
over 10 years. LIS art. 12.3.e is the EUR 300 unit election already enrolled.
LIS art. 12.3.a and 12.3.d apply to sociedades laborales and associative
priority farms, which are entities, not individual taxpayers. LIS DA 18a.2
makes new electric-vehicle charging infrastructure that enters service in
periods starting in 2024, 2025 or 2026 freely amortizable, subject to the
technical project and the regional installation certificate (DA 18a.3). DA
18a.1 covers new electric vehicles, whose affectation in IRPF is governed
separately and is outside the accepted asset scope. LIS art. 102 (job-creating
ERD free depreciation) and DA 17a (renewable self-consumption) both depend on
the average workforce over the following 24 or 48 months. The product has no
canonical average-workforce (plantilla media) fact.

### Day-count convention versus AEAT worked examples

The accepted lifecycle ADR prorates every charge by service days over 365 or
366. The AEAT activity examples prorate by whole months (for example, p. 472:
x 1/12 for a machine entering service on 1 December). The statute prescribes
neither. For intervals that are not whole calendar months, the day-count
result differs from the monthly result: 31/365 exceeds 1/12.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md` (LIS arts. 12, 101-103, DA 17a, DA 18a); https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328
- `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md` (RIS arts. 3-7); https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md` (LIRPF arts. 28-30)
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md` (RIRPF arts. 28-30)
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md` pp. 451-472; https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf
