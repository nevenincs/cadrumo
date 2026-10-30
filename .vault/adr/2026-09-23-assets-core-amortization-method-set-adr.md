---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:55084abf93c38e6581a2f8e54899a449c10543a1d9a89e995b064d5a7266d954'
related:
  - "[[2026-09-23-assets-core-amortization-method-set-research]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - '[[2026-09-23-assets-core-vehicle-affectation-research]]'
  - '[[2026-09-23-assets-core-proration-and-incentive-scope-research]]'
  - '[[2026-09-24-assets-core-amortization-domain-grounding-research]]'
  - '[[2026-09-27-registry-conformance-rectification-research]]'
---

# `assets-core` adr: `IRPF activity amortization method set and election contract` | (**status:** `accepted`)

## Problem Statement

The 2025 activity-asset engine enrols only the linear table maximum and the
EUR 300 election. `2026-09-23-assets-core-amortization-method-set-research`
shows that the normal modality admits four further LIS art. 12.1 methods, the
art. 12.2 intangible limits and several incentives, while the simplified
modality restricts material assets to the linear table. The current forecast
also receives its regime, class and method in a per-call selector, although
`2026-09-21-assets-core-lifecycle-contract-adr` requires the immutable
revision to carry classification, regime and method. A method whose charge
depends on the asset's position in its life cannot be chosen afresh on every
call. Linear charges also apply the rate to a base that still includes the
residual value, which RIS art. 3.2 excludes.

## Considerations

- A method is an election about the asset, and changing it must leave an
  auditable, superseding revision.
- Method admission differs by regime, asset kind and table class, and it
  belongs in typed registry authority rather than in Python branches.
- Constant percentage, sum of digits and plans depend on prior effective
  claims and on the in-service anniversary, not only on the covered interval.
- Free-depreciation amounts are chosen per tax period, within legal limits.
- The accepted day-count proration governs linear allocation. AEAT examples
  prorate by months; see the research record.

## Considered options

### Extend the per-call selector with method parameters

Rejected. It keeps the lifecycle-ADR deviation, allows a different method on
every forecast, and cannot reproduce which election a claim followed except
through the selector the caller happened to send.

### Carry the election on the immutable revision

Accepted. The revision owns regime, table class, method, its parameters and
the asset's new or used condition. A method change is a correction revision,
whose admissibility can be judged against the claims recorded under earlier
revisions.

## Constraints

- Filing-grade support remains tax year 2025, common-regime direct
  estimation, and material and intangible activity assets.
- Each admission, coefficient, threshold, weighting and window is a Modelo 100
  2025 registry parameter with legal references and AEAT manual citations.
  Absent registry rows mean unsupported. A row valued zero means excluded by
  law and refuses with its provision.
- No caller-authored rate or amount is accepted except an elected coefficient
  or free-depreciation amount bounded by registry authority, or a plan
  distribution bound to its administrative approval.
- There is no released compatibility floor; persisted histories without an
  election are not migrated.

## Implementation

`ActivityAssetRevision` gains a required amortization election (regime,
authority class key, method, method parameters, and optional ERD and
incentive evidence) and an acquired condition (new or used, with a building
construction date for used buildings). The per-call authority selector is
deleted. A forecast takes the asset, the covered interval and, for free
methods only, the elected amount.

The resolver reads the revision's election against the 2025 Modelo 100
parameters. It checks method admission for the regime and asset kind, class
admission for constant percentage and sum of digits, coefficient bounds
(maximum coefficient, the coefficient implied by the maximum period, the
multi-shift formula, the used-asset double maximum, ERD double maximum),
weighting bands with the 11% floor, R&D and charging windows, and the EUR 10
million ERD turnover threshold. It emits one typed schedule authority.

The amortizable base is the allocated basis minus residual value for every
method. Charges are exact Decimal and are rounded to cents at emission, then
capped at the remaining base.

- Linear, indefinite-life intangible, goodwill and R&D building methods
  charge the base times the resolved annual rate, times the service days in
  the interval over the tax-year days. This is the lifecycle ADR's rule.
- Constant percentage charges the percentage times the pending value at the
  start of the tax year (base less opening history and effective claims before
  that year), prorated the same way. In the tax year in which the useful life
  implied by the elected coefficient ends, the whole pending value is spread
  over the service days up to that end.
- Sum of digits assigns digits to life years that begin on the in-service
  date and on each anniversary, descending or ascending. A life year's quota
  is spread over its own days. This is the only reading in which a
  mid-year start keeps both the elected period and a total equal to the base.
- An approved plan charges the distribution the approval fixes for the tax
  year, spread over that year's service days. It applies only to tax years
  ending after the plan's submission.
- A definite-life intangible spreads the base over the days from in-service to
  the evidenced end of its useful life.
- The EUR 300, R&D and charging-infrastructure free methods claim the elected
  amount, which cannot exceed the remaining base; the EUR 300 annual cap check
  is unchanged.

A claim's election is that of the revision it references. Within one tax year
every effective claim for an asset must share one election fingerprint. A
correction may change the method only from a tax-year boundary. Constant
percentage and sum of digits are admissible only when no effective claim
under another election exists for the asset, because their formulas run
from the start of amortization.

Typed refusals cite their provision: the justified-amount method (LIS art.
12.1.e) because this decision's parent refuses caller amounts it cannot
validate; job-creating ERD free depreciation (LIS art. 102) and renewable
self-consumption free depreciation (LIS DA 17a) because no canonical average
workforce fact exists; electric vehicles (LIS DA 18a.1) because vehicles are
outside the accepted asset scope; sociedades laborales and associative
priority farms (LIS art. 12.3.a/d) because they are entity regimes; and ERD
acceleration of indefinite-life intangibles and goodwill because LIS art.
103.5 and the AEAT manual disagree on its scope.

## Rationale

Carrying the election on the revision is the accepted lifecycle contract. It
gives each life-dependent method a stable input, and it makes a change of
method an explicit, reviewable correction. Registry admission tables keep
regime and class restrictions as cited authority, so a new year or a legal
change is data, not code.

## Consequences

- CLI and TUI forecasts no longer accept an authority selector; revision JSON
  carries the election, and existing unit and acceptance fixtures must author
  it.
- Linear charges with a non-zero residual value decrease to the lawful base.
- The day-count versus monthly-proration divergence from AEAT examples
  remains a recorded inconsistency, to be resolved by amending the lifecycle
  ADR rather than by this record.
- Each refused incentive names the exact missing fact or conflicting source
  that would have to change before it can be enrolled.

## Amendment 2026-09-23

Authorized by the operator's coordinator on 2026-09-23 after further evidence
in `2026-09-23-assets-core-proration-and-incentive-scope-research` and
`2026-09-23-assets-core-vehicle-affectation-research`. The accepted body above
is preserved; where it differs, this section governs.

- Constant percentage and sum of digits are admitted for the intangible classes
  the LIS art. 12.1.a table lists (software, audiovisual productions) in the
  normal modality: LIS art. 12.1 applies both methods to intangible assets and
  RIS arts. 5.2 and 6 exclude only buildings, furniture and fittings. In the
  simplified modality they stay refused, the refusal naming the sources that
  leave the weighted table undetermined.
- Reduced-size acceleration of indefinite-life intangibles and goodwill is
  admitted at 150% of the LIS art. 12.2 one-twentieth for elements acquired in
  a period meeting LIS art. 101, new or used, as the binding DGT consultas and
  the AEAT manuals read the stale art. 103.5 cross reference; the registry
  parameter carries that reading as its provenance.
- Electric-vehicle free depreciation (LIS DA 18a.1) is admitted for new
  annex-II vehicles entering service in 2024 or 2025, on a vehicle affectation
  declaration that `2026-09-23-assets-core-vehicle-affectation-adr` admits.
- The day-count proration of the lifecycle decision is the unit binding
  consulta V1978-24 states; the AEAT examples' month fractions are
  illustrations, so the recorded inconsistency is resolved without amending
  the lifecycle decision.
- Job-creating ERD free depreciation (LIS art. 102) and renewable
  self-consumption free depreciation (LIS DA 17a, 2025 entries only for the
  2025 IRPF period) remain refused until the average-workforce profile fact
  lands; that fact is scheduled in the taxpayer profile schema version 7.

## Amendment 2026-09-27

Authorized by the operator's registry conformance rectification brief of 2026-09-27, recorded as the approval basis of `2026-09-27-registry-conformance-rectification-plan`, on the evidence in `2026-09-27-registry-conformance-rectification-research`. The accepted body above is preserved; where it differs, this section governs.

- Filing-grade support extends from tax year 2025 to every year of the registry support envelope, floor 2022. The amortization parameters are authored once at the first edition the law admits them and later editions key only their own manual evidence or a genuine change; the tables, thresholds and general methods are the same in every supported year.
- Renewable self-consumption free depreciation (LIS DA 17a) is admitted from 2023, with entry into service in the tax year; 2022 admits it for no installation. Electric-vehicle and charging-point free depreciation (LIS DA 18) is admitted from 2024; the 2023 DA 18 regime is accelerated depreciation, which stays outside the method set. A year no authored edition covers admits no incentive whose enactment is annual.
- The resolver serves a year through the canonically selected Modelo 100 edition, projected where no edition is authored, and refuses only an edition that begins after the tax year.

## Amendment 2026-10-30

Authorized by the operator on 2026-10-30, who directed reconciliation of the amortization decisions with no divergent routes and a settled legal basis, on the evidence in `2026-10-30-assets-core-amortization-law-and-form-placement-research`. The accepted body and earlier amendments are preserved; where they differ, this section governs.

- Years and projection: `2026-08-27-registry-dated-validity-adr` keeps its exact-year refusal for the corpora it migrated and excludes Modelo revision directories, so it does not govern this resolver. The temporal-coverage gate of `2026-08-14-registry-temporal-coverage-adr` still governs a filing-grade Modelo 100 snapshot. A projected edition therefore serves an asset forecast and the Modelo 130 of that year, and it does not admit a Modelo 100 of a year without its own edition.
- Incentive windows: each year admits only that year's entries into service, which reads the 2026-09-23 and 2026-09-27 wording as one rule. For IRPF 2025, LIS DA 17 rests on RDL 16/2025 with the AEAT note and remains an advisory gap, and LIS DA 18 rests on RDL 4/2024. RDL 7/2026 art. 37 reaches only periods not concluded at 22 March 2026, so it does not ground IRPF 2025. It grounds 2026 once a 2026 edition authors those parameters; until then a projected 2026 admits neither incentive.
- Workforce methods: the refusal of job-creating and renewable free depreciation ended when the fact of `2026-09-24-assets-core-average-workforce-write-path-adr` landed. They are admitted under their registry conditions.
- Regimes: this method set covers direct estimation. Estimación objetiva stays refused until it has its own table and destinations. It is a later slice, not a mode of these methods.
- Proration: days of operation over days of the year for every method. The 2026-09-23 ground is withdrawn, because V1978-24 concerns a first-year quota in módulos and says nothing on direct estimation or quarters. The rule rests on RIS art. 4.1, which makes the table a corridor between the maximum coefficient and the one derived from the maximum period, and on the precedence of regulation over manual examples. The days figure is the maximum, and a month-based example below it is a lawful lower amount: 36,000 at 24% for December allows at most 733.81 and admits the manual's 720. That is reached through an elected coefficient inside the corridor, never through a caller-stated amount, and the oracle is tested as admissible rather than as the ceiling.
- EUR 300 test: the valor unitario is the precio de adquisición under NRV 12.ª, so it includes non-deductible IVA and excludes deductible IVA.
- Free depreciation not taken: it cannot be taken later for that year by rectification, and it remains available in later years within its conditions. The source, TEAC 01524/2017, was read through a secondary report, so its original must be read before this rule is cited in product text.
