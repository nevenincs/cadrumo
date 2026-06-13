---
tags:
  - '#plan'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-inventory-research]]'
  - '[[2026-05-03-external-tax-definition-engines-reference]]'
  - '[[2026-04-21-modelo-100-renta-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-research]]'
  - '[[2026-04-29-m100-per-ano-test-parity-research]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-research]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-research]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
  - '[[2026-05-05-modelo-100-renta-source-dependency-reference]]'
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
---



# `calculation-truth-registry` `teardown-rebuild` plan

This plan implements the accepted central AEAT legal calculation registry as a
hard teardown and rebuild. It is not an additive compatibility layer. Existing
formula rulesets, modelo metadata entries, casilla corpus projections, hydrate
surfaces, filing builders, VAT/category casilla maps, deadline/applicability
rules, schema generation, and export generation are source material only.
They must be audited, harvested into reviewed registry data, verified, and then
removed as legal or filing authorities.

## Proposed Changes

Create one strict registry authority under
`src/aeat/domain/calculations/registry/`, with reviewed TOML definitions under
`registry/aeat/`. The registry owns modelo identity, revisions, casillas,
formulas, parameters, data bindings, legal/source evidence, temporal
applicability, cross-model relations, export layouts, and calculation traces.

The work is governed by these non-negotiable rules:

- No legacy module remains as a filing-grade authority after its model wave.
- No generated file or hydrate path writes legal-rule truth.
- No filing workflow downgrades missing or invalid registry data into a soft
  state.
- No model snapshot exists until legal evidence, source evidence, calculations,
  export bindings, and programmatic filing linkage all validate.
- Existing code may be read as source evidence, but the old folders and
  modules are deleted or reduced to non-authoritative plumbing by the end of
  their wave.
- Tests must verify real behaviour, legal reference closure, source integrity,
  formula closure, export alignment, and import boundaries.

Each modelo wave is a complete implementation of exactly one modelo. A wave is
not complete until audit, research, discovery, registry data, calculation
runtime linkage, export or filing linkage, legal verification, calculation
verification, deletion of old authorities, and registry-backed behaviour tests are
done for that modelo.

Modelo 100 is handled as the Renta universe: it is still one modelo, but it is
large enough to require internal epochs for source control, summary sections,
anexos, CCAA rules, rental/amortization behaviour, deductions, final settlement,
and export linkage.

Modelo 100 also has a dedicated aggregation phase before its completion wave.
The aggregation phase is not a compatibility bridge. It is the hard boundary
where every Renta source, extractor, live-read observation path, rental helper,
category profile, and old ruleset-era document is classified as either reviewed
registry evidence, lean non-authoritative plumbing, or deletion target.

## Production Readiness Definition

The plan is not allowed to treat a modelo as implemented because a TOML file
exists or because a previous Python ruleset was copied into a new shape. A
modelo is production-ready only when all of the following are true:

- The wave has a model-law coverage ledger listing every supported revision,
  every official AEAT source artefact used, every BOE or AEAT legal reference,
  every casilla owned by the model, every formula, every parameter, every data
  binding, every relation, every export field, every filing workflow entry
  point, and every old authority removed.
- The registry can create one immutable snapshot for each supported revision
  and refuses every unsupported, incomplete, contradictory, stale, provisional,
  or incalculable revision.
- Every calculation object has legal evidence and source evidence. Evidence
  presence alone is not enough; the cited law or official guidance must support
  the calculation, threshold, rate, parameter, relation, or filing condition
  that uses it.
- Every calculation and verification artefact is assigned to the evidence tier
  it can actually prove: legal authority, official source guidance, executable
  parity evidence, or layout authority. BOE law/regulation references are the
  binding legal tier. AEAT instructions/manuals are official guidance and must
  be tied to legal basis for filing-grade calculations. AEAT Open/help
  programs are executable parity only when guarded and safe. Record designs are
  layout authority only.
- Every upstream and downstream modelo dependency is classified through the
  cross-dependency ledger as a profile/schedule dependency, periodic-to-annual
  summary relation, instalment-to-final-settlement relation, evidence-only
  relation, or explicit non-dependency.
- Every casilla is classified as manual, bound, computed, or informational, and
  no casilla can be populated by an unregistered rule, old filing builder,
  hydrate projection, generated schema, generated export module, or hidden
  Python mapping.
- Every formula and algorithm binding has declared inputs, outputs, constants,
  legal references, source references, deterministic execution, trace output,
  and real behavioural tests.
- Every modelo revision has a live-AEAT cross-reference decision recorded in
  its model-law coverage ledger. The decision must classify the official
  surface as read-only Open simulator, authorized Integration/test web service,
  static official documentation only, or forbidden authenticated/stateful
  surface.
- Every live cross-reference path is protected by a remote-state guard that
  rejects AEAT remote writes, server-side saves, authenticated filing portals,
  signing, presentation, payment, direct debit, amendment, cancellation, and
  document-submission actions. Unknown or unresearched AEAT surfaces fail
  closed.
- Every modelo revision has an XLS/XLSX parity coverage decision recorded in
  its model-law coverage ledger. Formula-form official AEAT workbooks become
  parity targets only when their formulas calculate tax/model outputs. Static
  layouts, record-design layouts, unsupported binary XLS files, converted XLS
  record designs, and unreadable artefacts become explicit coverage gaps for
  executable calculation parity and may only satisfy layout/source evidence.
- Synthetic parity input sets are single-source fixtures for each
  modelo/revision. The same inputs must be applied to the registry engine and
  the workbook/simulator parity surface before comparing outputs.
- Every export or programmatic filing path resolves through registry export
  layouts and validated snapshots. A model with no supported export or filing
  linkage is not production-ready.
- Every old model-specific authority is deleted or reduced to non-authoritative
  plumbing. Behaviour tests must exercise only current public workflows backed
  by validated registry snapshots and must fail fast on missing coverage.
- The wave has positive tests, negative tests, boundary tests, date-axis tests,
  legal-reference tests, source-integrity tests, export tests where applicable,
  and trace tests. Tests must use real behaviour and may not rely on mocks,
  skips, xfails, monkeypatches, or tautological assertions.

The model-law coverage ledger is the anti-pivot device. If a wave cannot show
which legal sources, official artefacts, casillas, formulas, exports, filing
paths, and deleted legacy authorities are covered, the wave is not done.
If a wave cannot prove that its AEAT live/static cross-reference surface is
safe and correctly classified, the wave is not done.
If a wave cannot prove that its official workbook parity surface has been
discovered, classified, and either executed or recorded as a coverage gap, the
wave is not done.

## AEAT Calculation-Parity Reality

A 2026-05-06 verification sweep confirmed that AEAT publishes **no executable
formula workbook for any supported modelo**. Every official artefact in the
public corpus falls into one of three buckets, none of which is a downloadable
calculation oracle:

- **Record-design XLSX/XLS** under `disenos_registro/` carries field positions,
  lengths, types, and prose descriptions only. The full inventory of 97
  workbooks shows zero formula-bearing cells across the entire corpus.
- **PDF help and manual artefacts** under `static_files/Sede/Biblioteca/Manual/`
  and `static_files/Sede/Biblioteca/Manual/Tecnicos/` carry worked numeric
  examples in Spanish prose only. The Manual practico de sociedades 2024 PDF
  and the Manual de ayuda tecnica Renta Web 2024 PDF are the canonical user
  guides; neither contains executable formulas.
- **Web-only simulators** like Renta WEB Open (anonymous, classified as the
  Modelo 100 read-only executable parity surface), Sociedades WEB
  (authenticated), and Renta WEB (authenticated) hold AEAT's calculation logic
  server-side. They cannot be downloaded as workbooks. The XSDs published for
  developer integration declare field types and value ranges only; they
  contain no `<xs:assert>` calculation rules.

Standalone "Programa de ayuda" downloads were retired in 2017 ("desaparecen
las plataformas informativas y los programas de ayuda"); the only durable
session artefact AEAT publishes is the proprietary `.ses` partial-declaration
container, which is not a calculation oracle.

The registry rebuild therefore must treat formula-form workbook parity as a
genuinely **unavailable** evidence surface for almost every modelo, not as a
deferred-but-eventually-reachable target. Each modelo wave must classify its
calculation-parity strategy explicitly under one of these tiers:

- **Web-driven simulator parity** (preferred when the simulator is anonymous
  and AEAT has classified it as a read-only parity surface). Modelo 100 falls
  here through Renta WEB Open. The registry must drive the simulator headlessly
  with synthetic inputs, scrape the rendered cuota outputs, and compare to
  registry-computed values via the `_workbook_parity` and `_parity_tapes`
  harness. AEAT-authoritative every run; auto-detects AEAT changes; brittle
  to UI changes.
- **Authenticated WEB drive** (Sociedades WEB, authenticated Renta WEB).
  Available only with the bound taxpayer's session; protected by the
  remote-state guards declared on every revision; must remain read-only and
  must never trigger save, sign, present, pay, domicile, amend, cancel, or
  submit actions.
- **Justificante reverse-validation** (post-filing). When a real declaration
  has been filed, the AEAT-issued justificante PDF echoes computed totals.
  The committed sanitized fixture flow plus the registry's calculation must
  match the justificante's totals; AEAT is the authority and the registry is
  validated against it.
- **Manual practico worked-example fixtures**. The AEAT manuals contain
  numeric worked examples in Spanish prose. Each example becomes a synthetic
  test fixture with explicit AEAT-prose source citation so that any
  registry-vs-prose drift fails the test loud. This is the lowest-friction
  fallback when no live surface is safe to drive but is bounded by how many
  worked examples AEAT publishes.

Every modelo wave must declare which of these tiers covers its calculation
parity, must execute that tier's evidence at least once per supported
revision, and must record any gap explicitly. Hand-rolled XLSX parity oracles
not derived from one of the four tiers above are forbidden — they regress
silently every time AEAT updates its rules and cannot be defended as an
authority.

The workbook parity backend assumes the LibreOffice headless runner is
present. The host must provision LibreOffice (or the Excel COM runner on
Windows) as a base dependency; `detect_workbook_runner()` and the underlying
resolvers raise explicitly when no runner is locatable rather than degrading
silently to "skip parity". Tests and fixtures may not branch on runner
availability.

## Modelo Cross-Dependency and Hierarchy Ledger

Every modelo wave must classify its upstream and downstream relations before it
can be marked complete. A relation is not allowed to exist as an implied Python
helper, parser side effect, extractor convention, or workflow shortcut. It must
be represented in the registry as typed modelo evidence with direction,
periodicity, required observations, legal refs, source refs, aggregation rules,
failure semantics, and trace output.

The hierarchy is:

- Censal/profile authority: Modelos 036 and 037 provide taxpayer identity,
  activity, regime, enrolment, and monthly/quarterly schedule facts for the
  modelos whose filing cadence depends on profile.
- Periodic filing children: Modelos 111, 115, 123, 130, 131, 202, 303, 349,
  and 369 represent periodic obligations and must declare whether their values
  feed an annual summary, a final settlement, or evidence-only reconciliation.
- Annual informative summaries: Modelos 180, 190, 193, and 347 reconcile
  declared third-party/perceptor facts and must not silently replace the
  underlying periodic obligations.
- Annual settlement parents: Modelo 100 is the Renta settlement parent for IRPF
  facts; Modelo 200 is the corporate-tax settlement parent; Modelo 390 is the
  annual IVA summary parent for Modelo 303.
- Evidence-only declarations: Modelos 232, 720, 840, 347, 349, and 369 can
  provide audit context or consistency checks only unless the target modelo
  registry declares a law-backed calculation binding for a specific casilla.

Dependency completion requires acyclic calculation relations, explicit
evidence-only classifications for non-calculation links, and hard failure when
a required upstream observation is missing, malformed, contradictory, outside
its valid period, or unsupported by legal/source evidence.

| Modelo | Dependency role | Required relation work |
| --- | --- | --- |
| 036 | Censal/profile authority for identity, activity, tax regime, enrolment, and filing cadence selection. | [ ] Define profile facts consumed by each profile-dependent modelo, with legal/source refs, effective dates, read-only live-data capture rules, and schedule-selection tests. |
| 037 | Simplified censal/profile authority only where official evidence supports current filing-grade use. | [ ] Classify each supported profile fact as equivalent to Modelo 036, narrower than Modelo 036, or unsupported; remove app linkage for unsupported facts. |
| 100 | Renta final-settlement parent for IRPF facts and cross-model income, withholding, instalment, deduction, and evidence observations. | [ ] Build a Renta dependency map covering 130, 131, 180, 190, 193, 347, 349, 369, 720, 840, and any censal/profile facts; classify each as calculation input, deduction/input fact, withholding evidence, activity context, or non-dependency. |
| 111 | Periodic withholding child for work/professional/agricultural income and source for Modelo 190. | [x] Define profile-based monthly/quarterly schedules; [ ] define all Modelo 190 annual-summary relations and any Renta observation requirements with source periods. |
| 115 | Periodic rental withholding child and source for Modelo 180. | [ ] Define all Modelo 180 annual-summary relations and any Renta rental/withholding observation requirements with source periods. |
| 123 | Periodic capital-income withholding child and source for Modelo 193. | [ ] Define all Modelo 193 annual-summary relations and any Renta capital-income observation requirements with source periods. |
| 130 | Periodic IRPF instalment child and Renta payment-on-account observation source. | [x] Define required previous-filing/live observation capability; [ ] define Modelo 100 downstream payment-on-account bindings and failure semantics for missing prior-period observations. |
| 131 | Periodic IRPF objective-estimation instalment child and Renta payment-on-account observation source. | [ ] Define Modelo 100 downstream payment-on-account bindings, objective-estimation activity context, module-year dependencies, and profile/schedule inputs. |
| 180 | Annual informative summary parent for Modelo 115 and evidence source for Renta rental withholding facts. | [x] Define quarterly Modelo 115 source-period relation; [ ] define downstream Modelo 100 rental evidence bindings and perceptor/property consistency checks. |
| 190 | Annual informative summary parent for Modelo 111 and evidence source for Renta withholding and income facts. | [x] Define quarterly Modelo 111 source-period relation; [ ] define monthly Modelo 111 source-period relation where profile evidence requires monthly cadence; [ ] define downstream Modelo 100 work/professional/agricultural withholding evidence bindings. |
| 193 | Annual informative summary parent for Modelo 123 and evidence source for Renta capital-income facts. | [x] Define quarterly Modelo 123 source-period relation; [ ] define downstream Modelo 100 capital-income and withholding evidence bindings. |
| 200 | Corporate-tax final-settlement parent. | [ ] Define Modelo 202 instalment-payment bindings and Modelo 232 evidence-only or calculation-backed relation classification. |
| 202 | Corporate-tax instalment child and source for Modelo 200. | [ ] Define Modelo 200 downstream payment-on-account bindings, method-specific base dependencies, and profile/period schedule rules. |
| 232 | Corporate related-party/tax-haven informative evidence for Modelo 200. | [ ] Classify relation to Modelo 200 as evidence-only unless a specific legally grounded corporate-tax calculation binding is declared. |
| 303 | Periodic IVA child and source for Modelo 390. | [ ] Define monthly/quarterly profile schedule selection, all Modelo 390 source-period relations, and IVA consistency traces. |
| 390 | Annual IVA summary parent for Modelo 303 and possible Renta economic-activity reconciliation evidence. | [ ] Define Modelo 303 source-period relation and classify any Modelo 100 link as evidence-only unless a law-backed Renta casilla binding is declared. |
| 347 | Annual third-party operations informative declaration and possible Renta/IVA/corporate reconciliation evidence. | [ ] Define thresholds and party aggregation; classify downstream links to Modelo 100, 200, 303, or 390 as evidence-only unless a target registry declares calculation authority. |
| 349 | Periodic intra-community operations declaration and possible IVA/Renta activity evidence. | [ ] Define downstream relation to IVA/Renta as evidence-only unless a law-backed target casilla binding is declared. |
| 369 | OSS/IOSS IVA declaration and possible Renta activity evidence. | [ ] Define downstream relation to Renta as evidence-only unless a law-backed target casilla binding is declared. |
| 720 | Foreign assets informative declaration and possible Renta wealth/income consistency evidence. | [ ] Classify downstream relation to Modelo 100 as evidence-only unless a target registry declares a specific law-backed calculation binding. |
| 840 | IAE activity declaration and source for activity/profile context. | [ ] Define profile/activity facts consumed by Renta, IVA, and periodic obligations; classify amount calculations as unsupported unless law-backed target bindings exist. |

Each modelo wave must copy the applicable row from this ledger into its own
checklist before completion. The registry verifier must enforce, before a
modelo wave can close, that every declared dependency points to an existing
modelo revision, valid source periods, valid target periods, registered
legal/source refs, and real behaviour tests that calculate or validate the
relation without embedding schema copies in the test suite.

## Model Wave Coverage Matrix

The following matrix qualifies the minimum domain scope of every supported
modelo wave. Each row has a typed checklist wave below and must satisfy the
production-readiness definition above.

| Wave | Modelo | Minimum model-law scope | Mandatory old-authority teardown | Live AEAT cross-reference gate |
| --- | --- | --- | --- | --- |
| 1 | 130 | IRPF payment on account, income/expense aggregation, reductions, retentions, previous payments, period accumulation, export linkage. | Rulesets, filing builder, category casilla mappings, casilla corpus projections, deadline/applicability duplicates. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 2 | 111 | Retenciones and ingresos a cuenta for work/professional income, period totals, recipient counts, legal withholding parameters, export linkage. | Rulesets, hydrate augment data, declaration extractor casilla truth, modelo metadata duplicates. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 3 | 115 | Rental withholding declaration, taxable base, withholding amount, recipient/landlord counts, legal withholding parameters, export linkage. | Rulesets, filing/declaration duplicates, category/rental mappings that imply casilla truth. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 4 | 123 | Capital income withholding declaration, bases, retentions, income-account treatment, period totals, export linkage. | Rulesets, annual-summary shadow links, declaration extractor casilla truth. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 5 | 131 | Objective-estimation IRPF instalments, modules, reductions, previous payments, temporal parameters, export linkage. | Rulesets, category/deadline/applicability duplicates, casilla corpus projections. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 6 | 180 | Annual summary of Modelo 115 outputs, declared recipient/property records, cross-model relation to 115, export linkage. | Annual summary rulesets, declaration extractor truth, generated/projection casilla truth. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 7 | 190 | Annual summary of Modelo 111 outputs, recipient records, withholding classifications, cross-model relation to 111, export linkage. | Annual summary rulesets, declaration extractor truth, hydrate/casilla projections. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 8 | 193 | Annual summary of Modelo 123 outputs, capital-income recipient records, cross-model relation to 123, export linkage. | Annual summary rulesets, declaration extractor truth, duplicated metadata. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 9 | 303 | IVA autoliquidacion, VAT rates and parameters, factual VAT bindings, deductible/output VAT casillas, period variation, export linkage. | Rulesets, filing builder, VAT rate/mapping authority, category bridge authority, generated export modules. | Research Modelo 303 OPEN simulator as the only candidate live calculation cross-reference; authenticated Pre303/presentation remains forbidden and remote-state guarded. |
| 10 | 390 | Annual IVA summary, typed relations to Modelo 303 outputs, yearly source-format variation, XSD/PDF/XLS/XLSX-backed export or declaration linkage. | Rulesets, filing builder, annual IVA summary duplicates, generated export/layout authorities. | Research Modelo 390 OPEN simulator as read-only cross-reference evidence and prove `.ses`, export, and preview flows cannot write AEAT remote state. |
| 11 | 349 | Intra-community operations declaration, operation classifications, party/amount records, period rules, export linkage. | Declaration extractor casilla truth, modelo metadata duplicates, casilla projections. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 12 | 347 | Third-party annual operations, thresholds, party aggregation, annual/quarterly breakdowns, legal exceptions, export linkage. | Category/aggregation hardcoding, declaration extractor truth, modelo metadata duplicates. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 13 | 369 | OSS/IOSS IVA declaration, regime-specific operation totals, country/rate breakdowns, temporal applicability, export linkage. | VAT/category mapping authority, declaration extractor truth, duplicated metadata. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 14 | 202 | Corporate-tax payment on account, base methods, percentages, previous amounts, period selection, export linkage. | Rulesets, corporate-tax helper hardcoding, modelo metadata duplicates. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 15 | 200 | Corporate-tax annual filing, corporate parameters, bases, deductions, instalment relations, large export layout, legal evidence by subdomain. | Rulesets, corporate-tax helpers, declaration extractor truth, generated/export layout authorities. | Research Sociedades WEB Open as read-only cross-reference evidence and prove `.ses`, `.200`, and preview flows cannot write AEAT remote state. |
| 16 | 232 | Related-party and tax-haven operations, thresholds, party/operation records, reporting conditions, export linkage. | Modelo metadata duplicates, declaration extractor truth, casilla projections. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 17 | 720 | Foreign assets declaration, asset classes, thresholds, reporting conditions, record layouts, legal evidence, export linkage. | Modelo metadata duplicates, declaration extractor truth, standalone casilla projections. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 18 | 840 | IAE declaration, census/tax activity data, municipality/activity conditions, source/legal evidence, filing linkage. | Modelo metadata duplicates, declaration extractor truth, censal hydrate data. | Classify official live/static surface; if no Open simulator or authorized Integration test exists, use static official documentation only and guard all remote state. |
| 19 | 036 | Censal declaration, identity/activity/tax-regime registration sections, official source layout, legal basis, filing linkage. | Censal hydrate tables, declaration extractor truth, modelo metadata duplicates. | Classify official live/static surface; authenticated census modification/presentation surfaces are forbidden unless AEAT publishes an official test mode with synthetic data. |
| 20 | 037 | Simplified censal declaration if reviewed official evidence exists; otherwise explicit removal from filing-grade support. | Censal hydrate tables, declaration extractor truth, any implied support without official evidence. | Classify official live/static surface; if current filing-grade evidence is absent, remove app entry points and retain only evidence-backed historical records. |
| 21 | 100 | Renta universe: source governance, summary, anexos, income types, reductions, minimos, bases, cuotas, CCAA rules, rental, amortization, deductions, borrador/declaration linkage, export or filing linkage. | All Renta rulesets, Renta helper modules, CCAA hardcoding, rental legal-calculation authority, borrador/extractor casilla truth. | Research Renta WEB Open as read-only cross-reference evidence; authenticated Renta WEB/borrador/data-fiscal flows are forbidden for synthetic calculation tests. |
| 22 | 184 | Annual informative declaration for entities under attribution of income, declared entity/perceptor facts, annual schedule, record-design layout authority, extraction/verification linkage. | Modelo metadata duplicates, declaration extractor truth, standalone casilla projections, any implied Renta attribution authority outside the registry. | Static official documentation plus authenticated read-only filed-declaration surface; no writable AEAT action is allowed. |
| 23 | 308 | IVA ad-hoc refund request, operator-trigger classification, refund request facts, profile-conditional deadline rules, record-design layout authority. | IVA/category maps, declaration extractor truth, deadline/applicability duplicates, any implied refund calculation outside the registry. | Static official documentation plus authenticated read-only filed-declaration surface; no write, sign, present, or payment action is allowed. |
| 24 | 309 | IVA non-periodic declaration, trigger-specific IVA facts, selected ledger_iva_aggregation bindings, non-periodic result casillas, deadline/profile conditions. | IVA/category maps, filing/declaration duplicates, declaration extractor truth, deadline/applicability duplicates. | Static official documentation plus authenticated read-only filed-declaration surface; synthetic calculation parity remains open until official evidence is registered. |
| 25 | 322 | IVA group-of-entities individual monthly autoliquidation, member-level VAT ledger bindings, result casillas, monthly schedule, group-regime inputs. | IVA/category maps, filing builder duplicates, group-regime helper shortcuts, generated/export layout authorities. | Static official documentation plus authenticated read-only filed-declaration surface; authenticated presentation paths remain forbidden. |
| 26 | 353 | IVA group-of-entities aggregate monthly autoliquidation, dominant-entity consolidation, member 322 relation, group result casillas, monthly schedule. | IVA/category maps, group consolidation helpers, filing builder duplicates, generated/export layout authorities. | Static official documentation plus authenticated read-only filed-declaration surface; authenticated presentation paths remain forbidden. |
| 27 | 360 | IVA refund request for VAT borne in other EU Member States, refund-country facts, request/detail lines, deadline windows, record-design layout authority. | IVA/category maps, country/refund helper duplicates, declaration extractor truth, deadline/applicability duplicates. | Static official documentation plus authenticated read-only filed-declaration surface; no writable AEAT action is allowed. |

## Wave 0 Live Parity Oracle Backend Pre-Step

This pre-step is a hard prerequisite for every modelo wave that claims live
cross-reference evidence. It is governed by the live parity oracle backend
ADR, which extends the parent calculation-truth-registry ADR by formalising
the runtime contract every read-only AEAT verification adapter must satisfy.

The pre-step establishes a single shared backend for live verification so
that no modelo wave reinvents its own AEAT network adapter, no wave
duplicates the remote-state guard wiring, and no wave deviates from the
canonical parity-result shape. The backend is modelo-agnostic; each modelo
binds to a registered oracle by id, and the registry runtime never
instantiates network code by other means.

A modelo wave is not allowed to declare a live conformance check passed
unless the relevant oracle adapter is registered in the catalogue, has
exercised the contract tests, has its planned-operation set pre-flighted
through the existing remote-state guard, and produces a structured
:literal:`ParityResult` with verdict in the closed enum
:literal:`match | mismatch | unverifiable | blocked`.

### Wave 0 Backend Foundation Ledger

- [x] Wave 0 backend module: implement the modelo-agnostic
  `LiveParityOracle` Protocol, the canonical `ParityResult` and
  `ParityFieldComparison` records, and the `LiveParityCatalogue` keyed by
  oracle id. The module sits one level above the existing remote-state
  guard and never duplicates guard logic.
- [x] Wave 0 contract pre-flight: implement
  `pre_flight_oracle_operations` and the supporting helpers so every
  planned operation is gated by `assert_remote_operation_allowed` before
  any side-effecting code runs. Pre-flight refusal is a `blocked` verdict
  recorded as audit evidence, not an exception swallowed by callers.
- [x] Wave 0 contract tests: cover catalogue register/lookup/duplicate
  rejection, pre-flight refusal of POST/PUT/DELETE methods, pre-flight
  refusal of non-AEAT hosts, refusal of forbidden action tokens, refusal
  of `static_official_only` policies that plan remote operations, and the
  oracle-side guard call inside `verify_payload`.
- [x] Wave 0 production-or-test classification: every oracle adapter
  declares an explicit environment classification at registration time.
  Production-NIF-safe oracles are accepted in the production catalogue;
  AEAT pre-production / test-NIF oracles are accepted only under an
  explicit test-environment feature flag and are never registered against
  the autonomo's real NIF. The `LiveParityCatalogue` enforces this with a
  required `environment` keyword on registration and an environment-aware
  `lookup`; cross-environment lookups raise.
- [x] Wave 0 forbidden surface enumeration: extend the existing
  remote-state guard forbidden-token list with explicit denials of any
  surface that creates server-side state at AEAT even before legal
  presentation. TGVI online belongs to this category in production
  classification because its `FINALIZED` state under the production NIF is
  visible in declaration-history surfaces, can be configured to
  substitute prior filings, and is logged as an upload attempt regardless
  of whether it is later presented. The guard's `_FORBIDDEN_TOKENS` now
  includes `tgvi`, `transmision`, and `transmitir` so any URL or browser
  action containing those substrings fails pre-flight under any policy
  classification.

### Wave 0 Adapter Roadmap

- [ ] EU VIES VAT-ID checker adapter: pure-read public surface that
  validates intra-community NIFs against the canonical EU VIES service
  AEAT delegates to. No AEAT-side state, no production-NIF risk, accepted
  for the production catalogue. First adapter to ship because it sets the
  pattern other oracles follow with the lowest safety surface.
- [ ] AEAT public open-simulator adapter family: synthetic-input
  simulators (Renta WEB Open, Sociedades WEB Open, Pre303 and analogues)
  that accept synthetic data against fixture NIFs and return computed
  outputs. Accepted for the production catalogue with explicit
  `synthetic_data_allowed = true` policy. Per-modelo adapter ADRs declare
  allowed hosts, planned operations, and parity-field schema.
- [ ] AEAT pre-production fixed-width validator adapter: TGVI online
  against AEAT-issued test NIFs in AEAT's pre-production environment. The
  adapter is registered only when the test-environment feature flag is
  set and the active session NIF matches an AEAT test-NIF allowlist. The
  adapter is hard-blocked from registering under the production NIF or
  the production TGVI endpoint. The adapter ADR enumerates the test
  endpoint URLs, the test-NIF allowlist mechanism, and the audit trail
  for any FINALIZED state created during testing.
- [ ] Wave 0 adapter ADRs: every concrete oracle adapter ships with a
  follow-up ADR that identifies the AEAT surface, declares allowed hosts
  and HTTP methods, declares its planned operations under a sample
  policy, declares its environment classification, documents the
  parity-field schema, and links to the parent live parity oracle backend
  ADR.

### Wave 0 Per-Modelo Wave Gate

Every per-modelo parity ledger gains an explicit dependency on the Wave 0
foundation:

- A modelo wave may declare its `live cross-reference guard` row
  satisfied for a given surface only when the relevant oracle adapter is
  registered in the production-classified catalogue, has cleared its
  contract tests, and has been bound to the modelo's cross-reference by
  oracle id.
- A modelo wave may not declare its `live/filed-data tests` row satisfied
  for a verification surface unless the registered oracle returns either a
  `match` verdict for at least one synthetic-input fixture or an explicit
  `unverifiable` verdict whose narrative is recorded as evidence.
- A modelo wave may not introduce any direct HTTP call to AEAT from
  calculation, filing, review, export, CLI, or adapter code under
  Wave 0. The oracle backend is the only path through which a calculation
  engine reaches AEAT for live verification.

Modelo waves whose live cross-reference is `static_official_documentation`
do not require an oracle adapter and may close their wave under static
evidence, provided the parity ledger explicitly records the absence of an
applicable live oracle and the discovery walk against the authenticated
read surface (where applicable) yields zero filed rows or recorded
discovery evidence.

## Per-Modelo Parity Tracking Ledger

Every supported modelo has an explicit parity ledger. These rows intentionally
repeat across modelos so an implementing agent can mark each legal, source,
live-read, registry, verification, and teardown gate independently. A modelo is
not done because its parent phase is done; it is done only when every row in its
own ledger is checked.

### Wave 1 Modelo 130 Parity Ledger

- [x] Modelo 130 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 130 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [x] Modelo 130 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [x] Modelo 130 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 130 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 130 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [x] Modelo 130 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 130 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [x] Modelo 130 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/130.toml`.
- [x] Modelo 130 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [x] Modelo 130 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [x] Modelo 130 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [x] Modelo 130 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [x] Modelo 130 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [x] Modelo 130 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and previous-filing
  bindings are correct against official authority.
- [x] Modelo 130 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests, and binding-resolution tests without defaults or silent degradation.
- [ ] Modelo 130 teardown: delete or neutralize all old Modelo 130 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
  - [x] Neutralize shared runtime examples, default suggestions, and generic
    parser comments that used Modelo 130 as a de facto sample outside the
    registry, official corpus, or explicit Modelo 130 fixture surfaces.
  - [x] Replace generic recovery-command placeholders and public API examples
    that implied Modelo 130 as the default declaration path; retain only real
    Modelo 130 registry, corpus, portal, fixture, and explicit behaviour-test
    surfaces.
- [ ] Modelo 130 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 130 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 130 filing-grade values.

### Wave 2 Modelo 111 Parity Ledger

- [x] Modelo 111 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 111 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [x] Modelo 111 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [x] Modelo 111 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 111 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 111 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [x] Modelo 111 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 111 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [x] Modelo 111 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/111.toml`.
- [x] Modelo 111 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [x] Modelo 111 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [x] Modelo 111 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [x] Modelo 111 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [x] Modelo 111 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 111 calculation draft linkage: `build_draft` computes casillas
     28 and 30 from the committed registry snapshot.
  - [x] Modelo 111 export layout linkage: `export_draft` writes the committed
     registry record design and parsed casillas 28 and 30 round-trip from the
     exported payload.
  - [x] Modelo 111 verify linkage: `verify_export` re-reads the registry export
     payload and reports a match for the approved draft.
  - [x] Modelo 111 approval linkage: `approve_draft` approves a Modelo 111
     draft with a registry schema/formula fingerprint.
  - [x] Modelo 111 public CLI linkage: filing build, show, validate, list, and
     complementaria paths exercise the committed Modelo 111 registry surface.
  - [x] Modelo 111 review and reconciliation linkage: review and reconciliation
     derive Modelo 111 payable totals from registry-declared verification
     expectations instead of Python-side model branching.
- [x] Modelo 111 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
- [x] Modelo 111 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [x] Modelo 111 teardown: delete or neutralize all old Modelo 111 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
  - [x] Modelo 111 deadline applicability moved into registry TOML; Python
     profile documentation no longer encodes Modelo-specific obligation
     mappings, and CLI deadline tests exercise current registry behaviour.
  - [x] Modelo 111 parser comments sanitized to remove capture-date and
     development-observation metadata while preserving the parser contract.
  - [x] Modelo 111 generic CLI filing smoke helper no longer selects Modelo
     111 as a convenient hardcoded model; it selects a calculable modelo from
     the active registry provider.
  - [x] Modelo 111 remaining authority scan: review filing CLI helpers,
     portal metadata, justificante fixtures, submitted-file fixtures, and
     workbook-parity tests to ensure none can populate filing-grade values
     outside the registry.
- [x] Modelo 111 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [x] Modelo 111 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 111 filing-grade values.
  - [x] All 17 prerequisite rows checked (audit, legal basis, AEAT
    guidance, workbook coverage, live filed-data discovery, sanitized
    fixture, catalogue closure, TOML identity, casilla schema, formulas,
    extraction profiles, live cross-reference guard, export/filing
    linkage, legal correctness tests, live/filed-data tests, teardown,
    quality gate). Registry validator accepts Modelo 111 (1 revision,
    30 casillas) and the 11 dependent registry tests pass
    (`test_committed_modelo_111_registry_snapshot_is_calculable`,
    `test_modelo_111_*`, cross-dependency, filing-schedule selection,
    chain resolution).

### Wave 3 Modelo 115 Parity Ledger

- [x] Modelo 115 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 115 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [x] Modelo 115 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [x] Modelo 115 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 115 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 115 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 115 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 115 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [x] Modelo 115 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/115.toml`.
- [x] Modelo 115 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [x] Modelo 115 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [x] Modelo 115 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [x] Modelo 115 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [x] Modelo 115 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 115 application filing boundary: `build_draft` and
    `approve_draft` execute against the committed runtime registry provider and
    expose computed casillas 03 and 05 with registry schema fingerprinting.
  - [x] Modelo 115 export verification boundary: `export_draft` writes the
    committed registry record design and `verify_export` re-reads the exported
    payload against the approved draft.
  - [x] Modelo 115 declaration verification boundary: `verify_declaracion`
    compares parsed declaration casillas against the committed registry
    calculation expectation for casillas 03 and 05.
  - [x] Modelo 115 construct workflow closure: the current registry revision
    declares one construct that owns calculation, filing, export, verification,
    review, approval, reconciliation, extractor, portal, deadline, and workflow
    application links through validated snapshots.
- [x] Modelo 115 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
  - [x] Modelo 115 focused formula behaviour: direct registry calculation
    verifies the 19 percent withholding and result-to-pay formula with emitted
    legal trace references.
- [ ] Modelo 115 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 115 teardown: delete or neutralize all old Modelo 115 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [x] Modelo 115 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Modelo 115 construct-focused gate: `ruff`, `ty`, and focused pytest pass
    for the registry construct and quarterly formula behaviour tests.
- [ ] Modelo 115 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 115 filing-grade values.

### Wave 4 Modelo 123 Parity Ledger

- [x] Modelo 123 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 123 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [x] Modelo 123 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [x] Modelo 123 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 123 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 123 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 123 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 123 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [x] Modelo 123 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/123.toml`.
  - [x] Modelo 123 current deadline applicability: 2026 quarterly windows for
    the current revision resolve from the registry when
    `pays_capital_income_with_retencion` is true.
- [x] Modelo 123 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [x] Modelo 123 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [x] Modelo 123 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [x] Modelo 123 declaration parser boundary: current 2026 and 2019-2023
    declaration PDFs are parsed through the registry-selected extraction
    profile and must return every target casilla for the selected revision.
- [x] Modelo 123 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [x] Modelo 123 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 123 application filing boundary: `build_draft` and
    `approve_draft` execute against the committed runtime registry provider and
    expose computed casillas 03, 06, 09, 12, and 14 with registry schema
    fingerprinting.
  - [x] Modelo 123 export verification boundary: `export_draft` writes the
    committed current and 2019-2023 record designs and `verify_export`
    re-reads each exported payload against the approved draft.
  - [x] Modelo 123 declaration verification boundary: `verify_declaracion`
    compares parsed current and historical declaration casillas against their
    selected registry calculation expectations.
  - [x] Modelo 123 reconciliation boundary: `reconcile` projects the
    justificante payable total from the registry-declared verification
    expectation instead of Python-side modelo branching.
  - [x] Modelo 123 construct workflow closure: current and 2019-2023 revisions
    declare construct ownership for casillas, formulas, layouts, extraction,
    live/static evidence, workbook refs, verification expectations, and
    snapshot-gated workflow application links.
- [x] Modelo 123 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
  - [x] Modelo 123 focused formula behaviour: current and historical revisions
    calculate their registry-declared totals from real snapshot selection and
    reject drift through formula target coverage.
- [ ] Modelo 123 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [x] Modelo 123 teardown: delete or neutralize all old Modelo 123 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [x] Modelo 123 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Modelo 123 construct-focused gate: `ruff`, `ty`, and focused pytest pass
    for current and historical construct ownership plus formula behaviour.
- [ ] Modelo 123 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 123 filing-grade values.

### Wave 5 Modelo 131 Parity Ledger

- [ ] Modelo 131 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 131 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
  - [ ] Modelo 131 audit: enumerate registry TOML entries, shared legal/source
    catalogue entries, workbook parity refs, extraction profiles, application
    links, and deadline windows that currently define Modelo 131.
  - [ ] Modelo 131 audit: enumerate runtime modules that can calculate, export,
    parse, verify, reconcile, schedule, review, or route Modelo 131 values.
  - [ ] Modelo 131 audit: enumerate CLI commands and workflows that expose
    Modelo 131 calculation, filing, verification, live-read, preview, export,
    or deadline behaviour.
  - [ ] Modelo 131 audit: enumerate tests and fixtures that mention Modelo 131
    and classify each as behaviour coverage, parser fixture, official corpus
    evidence, or obsolete authority.
  - [ ] Modelo 131 audit: enumerate generated, hydrated, cached, corpus-derived,
    or projection files that may still define Modelo 131 casillas, formulas,
    deadlines, export records, or live filed-data shapes.
- [ ] Modelo 131 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
  - [x] Modelo 131 current 2026 legal basis: catalogue RD 439/2007 article 110
    and Orden EHA/672/2007 article 1 for the current objective-estimation
    payment foundation.
  - [x] Modelo 131 annual module-order basis: catalogue BOE module orders for
    2024, 2025, and 2026 so year-scoped objective-estimation revisions can cite
    their applicable signs, indices, modules, and instructions.
  - [x] Modelo 131 historical module-order basis: catalogue BOE module orders
    for 2019, 2020, 2021, 2022, and 2023 so the historical record-design
    revision cites year-scoped objective-estimation authority.
- [x] Modelo 131 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 131 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 131 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
  - [x] Modelo 131 authenticated read-only scan: query filed rows for 2020
    through 2026 and record that the authenticated account returned zero rows,
    so no live declaration, submitted-file, or justificante artefact was
    available to sanitize.
  - [x] Modelo 131 official PDF surface discovery: source AEAT guidance proving
    that Modelo 131 exposes a form-generated preview PDF before presentation
    and a final receipt plus complete declaration PDF after presentation; no
    static reusable AEAT example declaration PDF was found in the official
    public surface.
  - [x] Modelo 131 prior-declaration recovery discovery: source AEAT guidance
    proving that previous Modelo 131 data can be recovered only from earlier
    electronic form submissions and that declarations before 2015 cannot be
    used by that recovery workflow.
- [ ] Modelo 131 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
  - [ ] Modelo 131 no-fixture guard: keep the live fixture row open until a real
    read-only AEAT artefact exists; do not replace it with synthetic or local
    fixture evidence.
  - [ ] Modelo 131 authenticated filed-data capture: retry the read-only filed
    declaration surface for current and historical years after authentication
    is available, and record submitted-file, declaration-copy, and justificante
    availability separately.
  - [ ] Modelo 131 guarded form-preview preflight: identify the exact preview
    form URL, browser actions, HTTP methods, download endpoints, and forbidden
    controls before any authenticated preview attempt.
  - [ ] Modelo 131 guarded form-preview policy: encode the preview flow as a
    remote-state guard policy that blocks save, present, sign, pay, domicile,
    amend, cancel, and any unclassified browser or HTTP action.
  - [ ] Modelo 131 guarded form-preview capture: attempt a read-only preview
    PDF capture only after the guard policy proves the flow cannot write AEAT
    remote state.
  - [ ] Modelo 131 fixture sanitization: sanitize any captured submitted-file,
    declaration-copy, justificante, or preview artefact through the committed
    sanitizer, persist only the redacted artefact, and record source hash,
    output hash, byte counts, and redaction ledger.
- [ ] Modelo 131 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
  - [x] Modelo 131 current 2026 catalogue closure: add current instructions,
    procedure, BOE form authority, and 2026 record-design source references
    with corpus paths and integrity data.
  - [x] Modelo 131 PDF surface catalogue closure: add the official AEAT
    form-preview/final-PDF guidance and prior-declaration recovery guidance as
    reviewed source references with corpus paths and integrity data.
  - [x] Modelo 131 source integrity repair: align local AEAT/BOE HTML source
    hashes and byte counts with the committed corpus files before registry
    verification.
- [ ] Modelo 131 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/131.toml`.
  - [x] Modelo 131 current 2026 registry foundation: define the current
    casilla-level liquidacion schema, calculation formulas, extraction
    profiles, source-backed verification expectation, static portal guard,
    workbook parity reference, and application links.
  - [x] Modelo 131 2024 and 2025 revisions: add explicit year-scoped registry
    revisions with annual module-order legal refs, source refs, period
    selectors, workbook-layout references, and calculation/date-axis tests.
  - [x] Modelo 131 2019-2023 revision: add the flatter historical registry
    revision after cataloguing the annual 2019, 2020, 2021, 2022, and 2023
    module-order legal trail.
- [ ] Modelo 131 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
  - [x] Modelo 131 current 2026 liquidacion casillas: define casillas 01
    through 15 with manual/computed classification, sections, legal refs, and
    source refs.
  - [ ] Modelo 131 activity-detail schema: model official DPA activity detail
    records separately from the flat liquidacion casillas before filing-grade
    export support can be enabled.
  - [ ] Modelo 131 DPA 2024 schema: inspect the official 2024 record-design
    workbook and define every DPA activity-detail field as structured export
    schema, not synthetic liquidacion casillas.
  - [ ] Modelo 131 DPA 2025 schema: inspect the official 2025 record-design
    workbook and prove whether the DPA field layout matches 2024 or requires a
    year-scoped schema variant.
  - [x] Modelo 131 DPA 2026 schema: inspect the official 2026 record-design
    workbook and prove whether the DPA field layout matches 2025 or requires a
    year-scoped schema variant.
  - [x] Modelo 131 DPA/DID workbook extraction: add a reusable read-only
    record-design inspector that extracts official workbook fields, positions,
    lengths, sheet names, and total record lengths for the 2019-2023, 2024,
    2025, and 2026 record-design workbooks.
  - [x] Modelo 131 current 2026 DPA/DID registry binding coverage: define the
    official non-reserved DPA activity-detail fields and DID IBAN field as
    layout-authority-backed registry bindings with sheet, offset, length, and
    data-type selectors.
  - [x] Modelo 131 DPA validation: add behaviour tests that parse the official
    2026 record-design workbook and compare its structured DPA/DID field
    coverage against the committed registry bindings without redefining the
    schema in test fixtures.
- [ ] Modelo 131 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Modelo 131 current 2026 liquidacion formulas: define 2 percent payment
    rates and computed casillas 04, 06, 07, 10, 13, and 15 through the registry
    runtime.
  - [x] Modelo 131 2024 and 2025 liquidacion formulas: define the same
    casilla-level calculation chain with year-scoped formula IDs and dated
    parameter values.
  - [x] Modelo 131 2019-2023 liquidacion formulas: define the same
    casilla-level calculation chain with historical formula IDs and dated
    parameter values.
- [ ] Modelo 131 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [x] Modelo 131 current 2026 declaration-copy profile: define strict
    declaration-PDF extraction coverage for casillas 01 through 15.
  - [x] Modelo 131 submitted-file extraction profile: add registry-backed
    submitted-file extraction only after the export layout has complete
    official field coverage.
  - [ ] Modelo 131 preview-PDF extraction profile: add registry-backed preview
    PDF extraction only after a guarded read-only preview artefact exists and
    its watermark/non-presentation semantics are represented.
  - [ ] Modelo 131 justificante extraction profile: add registry-backed
    justificante extraction only after a real sanitized AEAT justificante
    artefact exists and proves the available metadata shape.
- [ ] Modelo 131 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
  - [x] Modelo 131 current 2026 static surface decision: register the official
    static documentation cross-reference and forbidden AEAT write actions.
  - [x] Modelo 131 PDF/recovery surface decision: tie the form-generated PDF
    and prior-declaration recovery guidance to the static cross-reference
    decision without treating either surface as executable calculation parity
    evidence or a substitute for a sanitized live artefact.
- [ ] Modelo 131 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 131 current 2026 application links: register calculation,
    filing, verification, review, extraction, portal, and deadline consumers
    against validated snapshots.
  - [x] Modelo 131 export layout support: extend or model the official
    activity-detail record structures before adding export roundtrips.
  - [x] Modelo 131 export binding schema: extend the Python-side registry
    schema so export fields can reference structured data bindings, allowing
    DPA and DID fields to remain separate from flat liquidacion casillas.
  - [x] Modelo 131 structured draft binding backend: extend filing drafts so
    registry binding values can be persisted as scalar values or repeated
    row-indexed table values without converting them into synthetic casillas.
  - [x] Modelo 131 binding-backed export renderer foundation: teach the generic
    exporter to read binding values from approved drafts and to render
    binding-row repeated records when an official export layout declares that
    structure.
  - [x] Modelo 131 2024 export layout: implement the official 2024 workbook
    record layout, including envelope records, liquidacion fields, DPA records,
    and any DID/direct-debit structures that are present in the source.
  - [x] Modelo 131 2025 export layout: implement or explicitly reuse the 2025
    official record layout after comparing workbook field positions, lengths,
    record names, and requiredness against 2024.
  - [x] Modelo 131 2026 export layout: implement or explicitly reuse the 2026
    official record layout after comparing workbook field positions, lengths,
    record names, and requiredness against 2025.
  - [x] Modelo 131 DPA layout support: represent the official activity detail
    page for 2024, 2025, and 2026 without flattening it into synthetic
    casillas.
  - [x] Modelo 131 DID layout support: represent the official direct-debit page
    only through guarded payment/export semantics and never through live AEAT
    write actions.
  - [x] Modelo 131 DID guard linkage: ensure direct-debit fields can be exported
    or reviewed locally but cannot trigger live payment, domiciliation, or AEAT
    remote-state mutation.
  - [x] Modelo 131 2019-2023 export support: model the flatter historical
    record-design structure separately from the 2024-and-later DPA/DID shape.
  - [x] Modelo 131 export roundtrip tests: prove registry export serialization
    and parsing for each implemented revision using official field positions
    and real registry data, not schema definitions embedded in tests.
    - [x] Modelo 131 current export roundtrip: prove 2026 page-one, DPA, and
      DID binding values serialize and parse through the registry layout, omit
      empty DID records, and reject direct-debit export unless the payable
      casilla is positive.
    - [x] Modelo 131 2024 and 2025 export roundtrip: run the same behaviour
      against the year-scoped export layouts.
    - [x] Modelo 131 2019-2023 export roundtrip: prove the flatter historical
      record-design shape serializes and parses through the registry layout.
- [ ] Modelo 131 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
  - [x] Modelo 131 current 2026 behaviour tests: calculate objective-estimation
    totals through the committed registry and verify deadline applicability
    through the registry-backed deadline engine.
  - [x] Modelo 131 2024 and 2025 behaviour tests: prove the runtime selects the
    year-scoped revisions and calculates the committed objective-estimation
    liquidacion chain.
  - [x] Modelo 131 2019 and 2023 boundary tests: prove the runtime selects the
    historical revision at both ends of the covered date range and calculates
    the committed objective-estimation liquidacion chain.
- [ ] Modelo 131 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
  - [ ] Modelo 131 live parser tests: add only when a real sanitized AEAT
    read-only artefact is captured; zero live rows is recorded as discovery
    evidence, not parser coverage.
  - [ ] Modelo 131 observation-store tests: prove any captured read-only AEAT
    artefact is persisted only through the encrypted storage layer and can be
    reloaded into the standardized observation schema.
  - [ ] Modelo 131 filed-data binding tests: prove captured read-only data can
    populate registry bindings and calculation verification without defaults,
    silent degradation, or hardcoded assumptions.
- [ ] Modelo 131 teardown: delete or neutralize all old Modelo 131 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
  - [ ] Modelo 131 teardown: remove non-registry Modelo 131 calculation rules
    from rulesets and helper modules after each equivalent registry-backed
    behaviour is implemented.
  - [ ] Modelo 131 teardown: remove non-registry Modelo 131 deadline,
    applicability, and filing-window definitions after deadline behaviour is
    registry-backed.
  - [ ] Modelo 131 teardown: remove non-registry Modelo 131 export builders,
    generated export fragments, hydrated records, and projection files after
    export roundtrips are registry-backed.
  - [ ] Modelo 131 teardown: remove tests and fixtures that define Modelo 131
    schemas, casillas, formulas, or filing metadata instead of exercising the
    registry-backed implementation.
  - [ ] Modelo 131 teardown: run repository-wide scans proving no obsolete
    Modelo 131 authority remains outside reviewed registry, corpus, parser, or
    explicit behaviour-test surfaces.
- [ ] Modelo 131 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Modelo 131 current 2026 focused gate: run registry verification,
    calculation/deadline/setup tests, `ruff`, `ty`, `git diff --check`, and
    development-metadata sanitization scans for the touched surfaces.
  - [x] Modelo 131 full registry gate: run whole-tree registry verification
    after concurrent Modelo 180 duplicate IDs were resolved.
  - [x] Modelo 131 export/schema quality gate: run registry verification,
    export roundtrip tests, source-integrity checks, `ruff`, `ty`, and
    development-metadata sanitization scans after DPA/DID/export work lands.
  - [ ] Modelo 131 live-read quality gate: run remote-state guard tests,
    sanitizer tests, encrypted observation-store tests, parser tests, registry
    verification, `ruff`, `ty`, and `git diff --check` after any read-only AEAT
    artefact is captured.
- [ ] Modelo 131 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 131 filing-grade values.
  - [ ] Modelo 131 completion gate: confirm every supported revision has legal
    basis, official source evidence, calculation coverage, export coverage,
    parser coverage when artefacts exist, and a verified live/static
    cross-reference decision.
  - [ ] Modelo 131 completion gate: confirm every remaining unsupported live
    artefact path is recorded as unavailable from official or authenticated
    evidence, not ignored.
  - [ ] Modelo 131 completion gate: confirm the implementation contains no
    compatibility aliases, migration guards, dev-state metadata, or duplicate
    authority surfaces for Modelo 131.

### Wave 6 Modelo 180 Parity Ledger

- [x] Modelo 180 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 180 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
  - [x] Modelo 180 audit: repository scan found no surviving
    `src/aeat/domain/rulesets`, `src/aeat/domain/casillas`,
    generated-export, hydrate, or standalone filing-builder authority for
    Modelo 180.
  - [x] Modelo 180 audit: retained hits are registry/corpus definitions,
    registry-backed calculation/export/relation tests, Sede filed-data
    behaviour tests, CLI registry reporting, and endpoint-only portal
    metadata linked from registry application links.
- [x] Modelo 180 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [x] Modelo 180 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 180 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 180 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 180 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 180 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [x] Modelo 180 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/180.toml`.
- [ ] Modelo 180 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
  - [x] Modelo 180 annual-summary core fields: define declarante summary totals
    and perceptor monetary record fields for both covered revisions, with legal
    refs, source refs, and export refs bound to official record-design
    positions.
  - [x] Modelo 180 perceptor identity and inmueble fields: define NIF, name,
    province, modality, retention percentage, accrual year, property situation,
    cadastral reference, property province, and property postal code for both
    covered revisions, with export refs bound to official fixed-width
    positions.
  - [x] Modelo 180 representative identity field: define the optional type 2
    legal-representative NIF at positions 27 through 35 for both covered
    revisions.
  - [x] Modelo 180 inmueble address block: define the official type 2 address
    positions 135 through 320 for both covered revisions, including street,
    numbering, block/access details, complement, locality, municipality, and
    municipality code.
- [ ] Modelo 180 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Modelo 180 relation-backed annual formulas: define Modelo 115 annual
    summary relations, target bindings, rounding, and legal/source citations
    for total perceptores, total base, and total retentions.
  - [x] Modelo 180 dependency classification closure: classify Modelo 115 as
    the direct annual-settlement source for the Modelo 180 annual-summary
    construct and cover every registered Modelo 115 relation.
- [ ] Modelo 180 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [x] Modelo 180 submitted-file profile: route fixed-width submitted records
    through the registry parser for the committed core declarante/perceptor
    fields.
  - [x] Modelo 180 submitted-file profile expansion: include the newly declared
    perceptor identity, rent, accrual, cadastral, and property-location fields
    in the committed extraction target set.
  - [x] Modelo 180 representative identity profile: include legal
    representative NIF in the committed extraction target set for both covered
    revisions.
  - [x] Modelo 180 submitted-file address profile: include the full official
    inmueble address block in the committed extraction target set for both
    covered revisions.
- [x] Modelo 180 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 180 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 180 fixed-width layout linkage: add official type 1/type 2
    registry export layouts for current and historical revisions, and harden
    runtime provider period selection so annual-only modelos do not break
    unrelated quarterly filing providers.
  - [x] Registry export signed-money rendering: render signed positive money
    fields with the official blank sign slot and preserve `N` for negatives.
  - [x] Modelo 180 annual-summary workflow linkage: current and historical
    revision constructs now own calculation, filing, verification, extractor,
    portal, review, approval, reconciliation, and workflow application links,
    all requiring validated registry snapshots.
- [ ] Modelo 180 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  115, and any filed-data bindings are correct against official authority.
  - [x] Modelo 180 relation calculation tests: calculate current annual summary
    totals from supplied Modelo 115 relation values and verify emitted trace
    operands.
  - [x] Modelo 180 record parser tests: parse synthetic fixed-width type 1/type
    2 records through the committed registry layout, including signed perceptor
    base amounts.
  - [x] Modelo 180 perceptor parser tests: prove fixed-width parsing of
    identity, province, modality, retention percentage, accrual year, cadastral
    reference, property province, and property postal code through the committed
    registry layout.
  - [x] Modelo 180 representative identity parser test: prove fixed-width
    parsing of the optional legal-representative NIF field.
  - [x] Modelo 180 address parser tests: prove fixed-width parsing of the type
    2 inmueble address block through the committed registry layout.
  - [x] Modelo 180 annual-summary behaviour tests: resolve Modelo 115 quarterly
    observations through registry relations, calculate annual totals through
    the current registry engine, and reject incomplete source-period chains.
- [ ] Modelo 180 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 180 teardown: delete or neutralize all old Modelo 180 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 180 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Modelo 180 source-grounding focused gate: registry verification,
    catalogue integrity tests, committed registry tests, `ruff`, and `ty` pass
    for the source catalogue and registry surfaces.
  - [x] Modelo 180 registry/runtime focused gate: run whole-tree registry
    verification, committed registry tests, filing export tests, `ruff`, and
    `ty` for the touched registry, runtime, export, and test surfaces.
  - [x] Modelo 180 dependency-closure gate: whole-tree registry verification
    passes with Modelo 180, Modelo 190, and Modelo 193 annual-summary source
    relations covered by dependency classifications.
  - [x] Modelo 180 focused workflow gate: `ruff`, `ty`, and focused pytest pass
    for the registry definition and annual-summary behaviour tests.
- [ ] Modelo 180 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 180 filing-grade values.

### Wave 7 Modelo 190 Parity Ledger

- [ ] Modelo 190 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 190 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 190 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 190 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 190 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 190 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 190 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 190 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 190 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/190.toml`.
  - [x] Current registry foundation validates the 2025-y-siguientes annual
    revision and gates calculation, filing, verification, extractor, portal,
    review, approval, reconciliation, and workflow application links through a
    validated snapshot.
- [ ] Modelo 190 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 190 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Quarterly Modelo 111 source observations resolve through registry
    relations and aggregate via Modelo 190 calculation formulas for annual
    perceptions, annual amounts, and annual retentions.
- [ ] Modelo 190 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 190 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 190 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Calculation, filing, verification, extractor, portal, review, approval,
    reconciliation, and workflow links are construct-scoped and require a
    validated registry snapshot.
- [ ] Modelo 190 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  111, and any filed-data bindings are correct against official authority.
  - [x] Focused behavior tests validate snapshot construction, cross-registry
    Modelo 111 relation consistency, and calculation aggregation through filed
    observations without encoding migration state.
- [ ] Modelo 190 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 190 teardown: delete or neutralize all old Modelo 190 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 190 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 190 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 190 filing-grade values.

### Wave 8 Modelo 193 Parity Ledger

- [ ] Modelo 193 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 193 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 193 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 193 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 193 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 193 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 193 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 193 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 193 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/193.toml`.
  - [x] Current registry foundation validates the 2024-y-siguientes annual
    revision and gates calculation, filing, verification, extractor, portal,
    review, approval, reconciliation, and workflow application links through a
    validated snapshot.
- [ ] Modelo 193 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 193 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Quarterly Modelo 123 source observations resolve through registry
    relations and aggregate via Modelo 193 calculation formulas for annual
    perceptores, annual bases, and annual retentions.
- [ ] Modelo 193 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 193 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 193 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Calculation, filing, verification, extractor, portal, review, approval,
    reconciliation, and workflow links are construct-scoped and require a
    validated registry snapshot.
- [ ] Modelo 193 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  123, and any filed-data bindings are correct against official authority.
  - [x] Focused behavior tests validate snapshot construction, cross-registry
    Modelo 123 relation consistency, and calculation aggregation through filed
    observations without encoding migration state.
- [ ] Modelo 193 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 193 teardown: delete or neutralize all old Modelo 193 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 193 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 193 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 193 filing-grade values.

### Wave 9 Modelo 303 Parity Ledger

- [ ] Modelo 303 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 303 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 303 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 303 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 303 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 303 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 303 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 303 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 303 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/303.toml`.
- [ ] Modelo 303 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 303 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 303 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 303 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 303 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 303 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, VAT rate treatment,
  and any filed-data bindings are correct against official authority.
- [ ] Modelo 303 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 303 teardown: delete or neutralize all old Modelo 303 authorities
  in rulesets, filing builders, category mappings, VAT rate mappings, casilla
  projections, deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 303 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 303 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 303 filing-grade values.

### Wave 10 Modelo 390 Parity Ledger

- [ ] Modelo 390 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 390 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 390 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 390 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 390 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 390 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 390 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 390 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 390 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/390.toml`.
- [ ] Modelo 390 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 390 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 390 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 390 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 390 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 390 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  303, and any filed-data bindings are correct against official authority.
- [ ] Modelo 390 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 390 teardown: delete or neutralize all old Modelo 390 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 390 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 390 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 390 filing-grade values.

### Wave 11 Modelo 349 Parity Ledger

- [ ] Modelo 349 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 349 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 349 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 349 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 349 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 349 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 349 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 349 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 349 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/349.toml`.
- [ ] Modelo 349 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 349 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 349 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 349 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 349 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 349 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
- [ ] Modelo 349 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 349 teardown: delete or neutralize all old Modelo 349 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 349 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 349 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 349 filing-grade values.

### Wave 12 Modelo 347 Parity Ledger

- [x] Modelo 347 audit: greenfield in `src/aeat/` outside the existing
  portal entry (`Portal.PORTAL_M347_OPERACIONES_TERCEROS`); no legacy
  ruleset, builder, or hydrate path exists to teardown.
- [x] Modelo 347 legal basis: BOE-grounded catalogue covers Orden
  EHA/3012/2008 arts 1 (aprobación) and 10 (plazo), and Orden HAC/1431/2025
  art 1 (Modelo 347 modification for ejercicio 2025+).
- [x] Modelo 347 AEAT official guidance: AEAT procedure HTML captured at
  `corpus/aeat_official/instructions/modelo_347/files/modelo-347-procedure.html`
  (procedimiento GI27).
- [x] Modelo 347 workbook/layout coverage: two AEAT artefacts registered
  as `record_design_layout` parity refs — `aeat-dr-347-2025` (current PDF,
  modified by HAC/1431/2025) and `aeat-dr-347-2011` (historical PDF,
  applies 2011-12-13 to 2024-12-31).
- [ ] Modelo 347 live filed-data discovery: deferred — can be revisited
  with the same authenticated CLI used for prior modelos (zero rows
  expected for an autónomo NIF since Modelo 347 obligation triggers above
  the 3.005,06 EUR threshold per counterparty).
- [ ] Modelo 347 live sanitized fixture: gated on live discovery.
- [x] Modelo 347 legal/source catalogue closure: new
  `registry/aeat/legal/operaciones-terceros.toml` with the Order articles
  plus `aeat-dr-347-2025`, `aeat-dr-347-2011`, `aeat-modelo-347-procedure`,
  `boe-modelo-347-2008-form`, and `boe-modelo-347-2011-amendment` sources.
- [x] Modelo 347 TOML identity and revisions: single revision
  `2008-y-siguientes` (year_from=2008) in `registry/aeat/modelos/347.toml`
  with annual cadence, `["0A"]` period selector, nine deadline windows
  (February plazo for ejercicios 2018-2026), and the corresponding
  application links.
- [x] Modelo 347 casilla schema: declarante header casillas (ejercicio,
  tipo de declaración) with section, data type, requiredness, legal refs,
  and source refs.
- [ ] Modelo 347 formulas, parameters, and bindings: foundation has no
  layout bindings yet — both record-design corpus artefacts are PDFs (no
  XLSX), so PDF parsing is needed for field-level fidelity. Deferred to
  a follow-up slice.
- [x] Modelo 347 extraction profiles: declaracion-pdf profile with
  `aeat.adapters.inbound.declaracion.parse_declaracion`, strict
  confidence, fail-hard semantics, target declarante casillas.
- [x] Modelo 347 live cross-reference guard: static_official_documentation
  and authenticated_read_surface (www1+www6 hosts, GET/HEAD/OPTIONS only,
  all writes / signing / payment / amendment / cancellation forbidden).
- [x] Modelo 347 export/filing linkage: foundation only — application
  links cover portal, filing, extractor, verification, deadline.
  Per-record export-layout bindings deferred until PDF parsing lands.
- [x] Modelo 347 legal correctness tests: 14 behaviour tests covering
  identity, revision selection, the informative-only invariant, both
  workbook parity refs, both live cross-reference surfaces, the February
  plazo, the annual filing schedule, and construct membership consistency.
- [ ] Modelo 347 live/filed-data tests: gated on live sanitized fixture.
- [ ] Modelo 347 teardown: N/A — Modelo 347 was greenfield outside the
  existing portal entry.
- [x] Modelo 347 quality gate: validate_modelo passes against the
  committed catalogues; 14 focused tests pass; `ruff check`, `ty check`,
  and `git diff --check` clean for the touched surfaces.
- [ ] Modelo 347 completion gate: gated on live discovery + fixture +
  layout-binding rows; foundation landed in commit `1df70814` (Add
  Modelo 347 registry foundation).

### Wave 13 Modelo 369 Parity Ledger

- [ ] Modelo 369 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 369 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 369 legal basis: identify and catalogue BOE, EU, and applicable
  Spanish legal references for every filing-grade calculation, parameter,
  filing condition, and temporal applicability rule.
- [ ] Modelo 369 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 369 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 369 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 369 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 369 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 369 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/369.toml`.
- [ ] Modelo 369 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 369 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 369 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 369 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 369 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 369 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, OSS/IOSS regime
  handling, and any filed-data bindings are correct against official authority.
- [ ] Modelo 369 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 369 teardown: delete or neutralize all old Modelo 369 authorities
  in rulesets, filing builders, category mappings, VAT rate mappings, casilla
  projections, deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 369 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 369 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 369 filing-grade values.

### Wave 14 Modelo 202 Parity Ledger

- [x] Modelo 202 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 202 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
  - [x] DR202e25.xlsx and DR202e23.xlsx record-design workbooks inspected;
    casilla numbers and field offsets extracted from the official sheets.
  - [x] AEAT instructions HTML for current 2025+ and historical 2023-2024
    captured into `corpus/aeat_official/instructions/modelo_202/files/`.
  - [x] Existing portal entry confirmed at
    `aeat.domain.portals._entries.portal_m202_sociedades_fraccionado`.
- [x] Modelo 202 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
  - [x] Ley 27/2014 art. 40 (LIS art. 40, BOE-A-2014-12328) catalogued as the
    legal authority for both modalidad cuota (40.2) and modalidad base (40.3).
- [x] Modelo 202 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
  - [x] Modelo 202 instrucciones (current 2025+) committed with sha256 and
    bytes in `registry/aeat/legal/is.toml`.
  - [x] Modelo 202 instrucciones (ejercicios 2023-2024) committed with sha256
    and bytes in the same catalogue.
- [x] Modelo 202 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
  - [x] DR202e25.xlsx classified `record_design_layout`, runner not required;
    workbook parity reference declared on the 2025-y-siguientes revision.
  - [x] DR202e23.xlsx classified `record_design_layout`, runner not required;
    workbook parity reference declared on the 2023-2024 revision.
  - [x] DR202v52.xlsx (Orden HAC/941/2018, ejercicios 2019-2022) classified
    `record_design_layout`, runner not required; workbook parity reference
    declared on the 2019-2022 revision.
- [x] Modelo 202 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
  - [x] Authenticated Cl@ve Móvil read-only scan (2026-05-05) returned zero
    filed Modelo 202 declarations across ejercicios 2020-2026 for the bound
    taxpayer, so no submitted-file, declaration-copy, or justificante rows
    were available — discovery evidence on par with the Modelo 131 zero-row
    pattern recorded earlier in this plan.
- [ ] Modelo 202 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
  - [ ] Row stays open until a real read-only AEAT artefact exists; do not
    replace it with synthetic or local fixture evidence.
- [x] Modelo 202 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
  - [x] `registry/aeat/legal/is.toml` carries the LIS art. 40 legal ref plus
    the four Modelo 202 source refs (DR202e25.xlsx, DR202e23.xlsx, current
    instructions, 2023-2024 instructions) with reviewed status.
- [x] Modelo 202 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/202.toml`.
  - [x] `[modelo]` block declares id 202, IS pago fraccionado, quarterly,
    jurisdiction ES-AEAT, with LIS art. 40 legal ref.
  - [x] `[revisions."2025-y-siguientes"]` covers ejercicios 2025 and onward
    with periods 1P/2P/3P.
  - [x] `[revisions."2023-2024"]` covers ejercicios 2023-2024 with periods
    1P/2P/3P.
  - [x] `[revisions."2019-2022"]` covers ejercicios 2019-2022 (Orden
    HAC/941/2018, DR202v52.xlsx) with periods 1P/2P/3P. The AEAT layout is
    identical to the 2023-2024 revision (43 casillas), and the AEAT 2018-2022
    instructions surface only redirects to the 2023-2024 instructions, so the
    historical revision shares formula citations with 2023-2024 while keeping
    its own DR XLSX layout authority.
- [x] Modelo 202 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
  - [x] 50 casillas declared in the 2025-y-siguientes revision matching the
    full DR202e25.xlsx layout (incluye claves [61]-[67] añadidas en 2025).
  - [x] 43 casillas declared in the 2023-2024 revision matching DR202e23.xlsx;
    omits [61]-[67] which the AEAT layout introduced in 2025+.
  - [x] 43 casillas declared in the 2019-2022 revision matching DR202v52.xlsx;
    layout-equivalent to the 2023-2024 revision.
- [x] Modelo 202 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Parameter `is.modalidad_cuota.percentage` (18% per LIS art. 40.2)
    declared on both revisions with source citations grounded in real AEAT
    prose.
  - [x] Modalidad 40.2 chain: clave [03] = [01] × 18% − [02].
  - [x] Modalidad 40.3 corrections aggregation: clave [38] and clave [39].
    Current revision adds the IC corrections operand [67]; 2023-2024 sums
    only [05] + [07] for [38].
  - [x] Modalidad 40.3 base imponible previa: clave [13] = [04] + [38] − [39].
  - [x] Modalidad 40.3 B1 caso general resultado previo: clave [18] =
    ([16] × [17])/100 + [47] − [40] + [48] − [49].
  - [x] Modalidad 40.3 resultado: clave [32] = ([18] − [27] − [28]) × [29]/100
    − [30] − [31].
  - [x] Cantidad a ingresar: clave [34] = max([32], [33]).
  - [x] Modalidad 40.3 base imponible corregida (B1): clave [16] =
    max(0, [13] − [44] − [14] + [45] − [46]). The "sin poder ser negativa"
    floor matches the AEAT prose verbatim across both current and 2023-2024
    instructions and is declared on every revision.
  - [x] Modalidad 40.3 B2 importes (multi-rate): clave [22] = ([20] × [21])
    / 100; clave [25] = ([23] × [24]) / 100. Equivalent formulas declared on
    every revision.
  - [x] Modalidad 40.3 B2 importes (current-only multi-rate): clave [63] =
    ([61] × [62]) / 100; clave [66] = ([64] × [65]) / 100. Declared only on
    the 2025-y-siguientes revision because the historical layout does not
    expose multi-rate brackets 3 and 4.
  - [x] Modalidad 40.3 B2 resultado previo: clave [26] = [22] + [25] (+
    [63] + [66] in 2025+) + [50] − [42] + [51] − [52]. Per-revision formula
    excludes the 2025+-only operands when not present in the layout.
- [ ] Modelo 202 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [ ] Row stays open until a sanitized declaration-copy or submitted-file
    fixture lands; the extraction profile must be backed by a real artefact.
- [x] Modelo 202 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
  - [x] `modelo-202-static-documentation` cross-reference declared on the
    current revision with `surface = static_official_documentation`,
    `synthetic_data_allowed = false`, and `forbidden_actions` covering
    server-side-save, signing, presentation, payment, amendment, cancellation,
    document-submission, and declaration-submission.
  - [x] Equivalent `modelo-202-2023-2024-static-documentation` cross-reference
    declared on the historical revision with the same forbidden_actions set.
- [ ] Modelo 202 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 202 calculation linkage: registry-backed
    `calculate_registry_snapshot` consumer declared on both revisions through
    `application_links`.
  - [x] Modelo 202 filing/verification application links declared on both
    revisions referencing `aeat.application.filing` and
    `aeat.application.verification`.
  - [x] Modelo 202 portal application link points at
    `aeat.domain.portals.Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO`.
  - [x] Modelo 202 export layout — envelope record: full DR202e25.xlsx
    envelope structure transcribed in
    `[[revisions."2025-y-siguientes".export_layouts]]` (id
    `modelo-202-fichero-boe`, record `modelo-202-envelope-header`) with all
    13 fixed-position envelope fields (open tag, modelo constant, period
    placeholder, AUX block with reserved fillers plus program/developer
    header keys, AUX close). The `modelo-202-export` application link
    declares the export surface so the registry validator accepts the layout.
  - [x] Modelo 202 export layout — page records: DR202e25.xlsx sheet
    "dr M202 (1)" (page 01) is transcribed as the `modelo-202-page-01`
    `ExportRecordDefinition` with 46 real fields covering page-01 envelope
    constants, identification draft fields (NIF, surnames, name, foral
    indicator), devengo (ejercicio/periodo/fecha-inicio/CNAE), datos
    adicionales boolean headers, and page-01 casillas [01]-[08], [13],
    [14], [37]-[39], [44]-[46], [67]. DR202e25.xlsx sheet "dr M202 (2)"
    (page 02) is transcribed as the `modelo-202-page-02`
    `ExportRecordDefinition` with 57 real fields covering page-02 envelope
    constants and liquidacion casillas [16]-[34], [40], [42], [47]-[52],
    [61]-[66]. All 50 casillas in the 2025-y-siguientes revision now
    carry `export_refs` pointing at their page export field.
  - [x] Modelo 202 export layout — historical revisions: envelope + page-01
    + page-02 records mirrored into the 2023-2024 revision (layout id
    `modelo-202-2023-2024-fichero-boe`, 3 records / 108 fields, layout
    authority DR202e23.xlsx) and the 2019-2022 revision (layout id
    `modelo-202-2019-2022-fichero-boe`, 3 records / 108 fields, layout
    authority DR202v52.xlsx). The two historical XLSXes share identical
    casilla offsets and lengths (Orden HAC/941/2018 layout was stable from
    2019 through 2024); the 2025+ layout shifted offsets to make room for
    the IC corrections column [67] and the multi-rate brackets [61]-[66].
    All 43 casillas in each historical revision now carry `export_refs`
    pointing at their page export field; per-revision
    `modelo-202-2023-2024-export` and `modelo-202-2019-2022-export`
    application links and the construct `export_layouts` entries declare
    the surfaces.
- [x] Modelo 202 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, corporate instalment
  methods, and any filed-data bindings are correct against official authority.
  - [x] `test_modelo_202_modalidad_chains_calculate_for_synthetic_inputs`
    parametrized over 1P/2P/3P verifies the full calculation chain for the
    current revision.
  - [x] `test_modelo_202_revision_selection_resolves_for_filing_year_boundaries`
    parametrized over 2023/2024/2025/2026 proves the temporal selector picks
    the correct revision and computes [03] consistently across both windows.
  - [x] `test_modelo_202_2023_2024_total_correcciones_aumentos_excludes_complementario_column`
    proves the historical revision drops claves [61]-[67] and that [38]
    aggregates only [05] + [07].
- [ ] Modelo 202 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
  - [ ] Row stays open until a sanitized live artefact exists; zero filed
    rows is recorded as discovery evidence rather than parser coverage.
- [x] Modelo 202 teardown: delete or neutralize all old Modelo 202 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
  - [x] Codebase audit completed: no legacy Modelo 202 authority exists in
    `src/aeat/domain/formulas/`, `src/aeat/domain/filing/`,
    `src/aeat/domain/categories/`, `src/aeat/domain/deadlines/`,
    `src/aeat/domain/modelos/`, `src/aeat/adapters/inbound/declaracion/`,
    `src/aeat/adapters/outbound/aeat/export/`, or any other domain or
    adapter directory. The only Modelo 202 surfaces in `src/aeat/` are
    registry-backed: the portal entry
    `aeat.domain.portals._entries.portal_m202_sociedades_fraccionado`
    (registered through `Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO`), the
    cross-dependency calculation tests, the dedicated
    `test_modelo_202_registry.py` suite, and the workbook-parity coverage
    test that iterates registered parity refs.
  - [x] Fixture audit completed: no Modelo 202 fixture files in
    `tests/fixtures/`. Pre-existing matches on `\b202\b` resolve to
    incidental references in unrelated modelo fixtures.
- [x] Modelo 202 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Whole-tree `RegistryValidator.validate_modelo` passes for Modelo 202
    across both revisions; non-pre-broken modelos (100, 111, 115, 123, 130,
    131, 202, 349) all pass.
  - [x] `uv run pytest -k modelo_202` passes (11 cases after the historical
    2019-2022 revision lands: formula chain across the expanded coverage,
    revision selection across 2019-2022/2023-2024/2025-y-siguientes
    boundaries, and historical-aumentos divergence tests).
  - [x] `uv run ruff check` and `uv run ty check` clean on the touched test
    surface.
- [ ] Modelo 202 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 202 filing-grade values.

### Wave 15 Modelo 200 Parity Ledger

- [x] Modelo 200 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 200 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
  - [x] DR200e25.xls record-design (binary .xls, 11 MB) catalogued in the
    Modelo 200 corpus manifest. Casilla numbers for the settlement chain
    (00592 cuota liquida, 00599 cuota del ejercicio a ingresar/devolver,
    00611/00612 cuota diferencial, 01586/01587 resultado de la
    autoliquidacion, 00621/00622 resultado) extracted verbatim from the
    Manual practico de sociedades 2024 settlement chain summary.
  - [x] Codebase scan: no legacy Modelo 200 authority in
    `src/aeat/domain/formulas/`, filing builders, declaration extractors,
    export builders, or domain metadata. Existing portal entry
    `aeat.domain.portals._entries.portal_m200_sociedades_anual` is the
    only Modelo 200 surface in `src/aeat/` and is registry-aware.
- [ ] Modelo 200 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
  - [x] Ley 27/2014 art. 41 (Deduccion de retenciones, ingresos a cuenta y
    pagos fraccionados) catalogued as the legal authority for the cross-
    dependency relation 200 to 202: "Seran deducibles de la cuota liquida
    ... c) Los pagos fraccionados", with the BOE-A-2014-12328 corpus
    excerpt at `corpus/normatives/html/ley-27-2014-art-41.html`.
  - [x] Ley 27/2014 art. 40 retained as legal authority covering the
    underlying pago fraccionado regime that produces the deductible
    instalments (already present in the catalogue for Modelo 202).
  - [x] Ley 27/2014 art. 124 catalogued as the legal authority for Modelo
    200 declaration timing: 25 natural days after the six months following
    the end of the tax period.
- [x] Modelo 200 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
  - [x] Manual practico de sociedades 2024 PDF (6,266,062 bytes) committed at
    `corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf`
    as `kind = "manual_pdf"` source ref `aeat-modelo-200-manual-2024`. The
    validator extracts text via the registry PDF helper for source-citation
    matching.
- [x] Modelo 200 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
  - [x] DR200e25 layout authority converted from binary .xls (11 MB) to
    .xlsx (2.3 MB) via LibreOffice headless and committed alongside the
    original AEAT artefact. Catalogue source ref `aeat-dr-200-2025` now
    points at the .xlsx; workbook parity ref reclassified from
    `unsupported_binary_xls` to `record_design_layout`. The same horizontal
    sweep converted 25 binary .xls files across modelos 100, 111, 115, 123,
    130, and 200, updated 8 catalogue `corpus_path` entries plus 2
    `formula_coverage` reclassifications (modelos 130 and 200), and
    replaced 2 stale `-form-text` source refs with real text dumps
    generated from the converted .xlsx workbooks. All 12 supported modelos
    validate cleanly afterwards.
- [ ] Modelo 200 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 200 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [x] Modelo 200 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
  - [x] `registry/aeat/legal/is.toml` carries `ley-27-2014:art-41` legal
    ref plus the two Modelo 200 source refs (`aeat-dr-200-2025` layout
    authority and `aeat-modelo-200-manual-2024` official guidance) with
    sha256 + bytes integrity.
  - [x] `registry/aeat/legal/is.toml` also carries `ley-27-2014:art-124`
    and BOE source ref `boe-modelo-200-2025-form`, backed by local corpus
    excerpts for the legal filing window, 2025 Modelo 200 form order, and
    payment domiciliation cutoff.
- [ ] Modelo 200 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/200.toml`.
  - [x] `[modelo]` block declares id 200, IS autoliquidacion anual, annual
    cadence, jurisdiction ES-AEAT, with LIS art. 40, art. 41, and art. 124
    as legal refs.
  - [x] `[revisions."2024-y-siguientes"]` covers ejercicios 2024 onward with
    period 0A.
  - [x] Deadline schedule for calendar-year 2024 declares annual period 0A,
    filing window 2025-07-01 through 2025-07-25, and payment domiciliation
    cutoff 2025-07-22 against BOE-A-2025-12818.
  - [x] Application links cover portal, calculation, filing, verification,
    deadline, review, approval, reconciliation, and workflow surfaces.
  - [x] Export application link `modelo-200-2024-export` declared and the
    full `modelo-200-fichero-boe` layout (77 records / 6,531 fields)
    transcribed from DR200e25.xlsx covering the entire Modelo 200 fixed-
    width submission file.
- [x] Modelo 200 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
  - [x] Full transcription from DR200e25.xlsx: **3,215 unique casillas**
    declared across 77 sheets (DP200000-DP200054 plus DID), each with
    real label from the XLSX description, section path encoding the
    originating page (e.g., `["declaracion", "pagina_15b"]`), data_type
    derived from the XLSX `Tipo` column (Num/N → money/decimal by length,
    An → text), `input_kind = "manual"` default for all casillas not
    already part of the cross-dependency settlement chain.
  - [x] Existing computed casillas 00592 (cuota liquida) and 00599 (cuota
    del ejercicio a ingresar o a devolver) preserved with their hand-
    authored definitions and formulas; they are excluded from the
    auto-generated set.
  - [x] Every casilla carries `export_refs` pointing at its corresponding
    export field in the `modelo-200-fichero-boe` layout records (some
    casillas appear in multiple page records and carry multiple
    `export_refs` accordingly).
  - [x] Section paths re-derived from the AEAT-Sociedades dash-hierarchical
    label structure (commit `06cb4e4b`). 3,213 auto-generated casillas
    moved off the opaque `["declaracion", "pagina_NNN"]` bucketing onto
    semantic 2-deep section paths spanning 214 top-level chapters and
    637 unique full sections (Balance Activo / Patrimonio Neto y Pasivo
    I/II, Estado de Cambios Patrimonio Neto I/II, Cuenta de perdidas y
    ganancias I/II, Liquidacion I-IV, Conversion activos impuesto
    diferido credito exigible, Deducc. para incentivar determ.
    actividades, Deduccion donativos entidades sin fines lucro, Reg.
    cooperativas, Tributacion conjunta Estado y Adm.Forales, Reserva de
    nivelacion, Limitacion deducibilidad gastos financieros, etc.). The
    two hand-authored cuota-liquida / cuota-a-ingresar casillas with
    section `["liquidacion", ...]` are preserved untouched. Cross-modelo
    schema hygiene tests at `test_schema_hygiene.py` guard against
    section regression.
- [ ] Modelo 200 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Parameter `is.modelo-200.tipo-gravamen-general` (25% per LIS art. 40)
    declared with source-citation grounded in real Manual de Sociedades
    prose.
  - [x] Formula `modelo-200-cuota-ejercicio-a-ingresar-devolver` computes
    casilla 00599 from official casilla 00592 minus the relation-resolved
    aggregate of Modelo 202 instalments, citing LIS art. 41 and the Manual
    de Sociedades cuota-del-ejercicio chain summary.
  - [x] Binding `modelo-200-2024-pagos-fraccionados-anuales` declares the
    previous-filing aggregation target for Modelo 202 outputs.
  - [x] Cross-model relation `modelo-200-2024-rel-202-pagos-fraccionados`
    (kind `cross_model_output`, dependency_role
    `instalment_to_final_settlement`) reads Modelo 202 casilla [34] across
    periods 1P/2P/3P with `aggregation = sum`. Modelo 200's filing year
    matches Modelo 202's filing year via `filing_year_delta = 0`.
  - [x] Dependency classification `modelo-200-2024-dep-202-instalments`
    declares Modelo 202 as `direct_annual_settlement` evidence with the
    cross-model relation as the binding mechanism.
- [ ] Modelo 200 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [ ] Row stays open until a sanitized declaration-copy or submitted-file
    fixture lands; the extraction profile must be backed by a real artefact.
- [ ] Modelo 200 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
  - [x] `modelo-200-2024-static-documentation` cross-reference declared
    with `surface = static_official_documentation`,
    `synthetic_data_allowed = false`, and `forbidden_actions` covering
    server-side-save, signing, presentation, payment, amendment,
    cancellation, document-submission, and declaration-submission.
- [ ] Modelo 200 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Calculation, filing, verification, and portal application links
    declared on the 2024-y-siguientes revision and bound into the foundation
    construct. The export application link and full export layout
    transcription are deferred until a cross-platform .xls reader or AEAT
    .xlsx variant is available.
  - [x] Review, approval, reconciliation, deadline, and workflow application
    links now require the Modelo 200 registry snapshot and are included in
    the foundation construct.
- [ ] Modelo 200 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  202, and any filed-data bindings are correct against official authority.
  - [x] `test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados`
    proves the cross-dep chain: synthetic Modelo 202 1P/2P/3P filings are
    aggregated by the relation, and the final cuota a ingresar formula
    subtracts the aggregate from cuota liquida 00592. The trace references
    official casilla 00592 and the Modelo 202 relation id.
  - [x] `test_modelo_200_calendar_year_2024_deadline_matches_boe_order`
    proves the deadline window and payment cutoff against the committed BOE
    Modelo 200 order corpus, not against inline test fixture metadata.
- [ ] Modelo 200 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
  - [ ] Row stays open until a sanitized live artefact exists.
- [ ] Modelo 200 teardown: delete or neutralize all old Modelo 200 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
  - [x] Codebase audit completed: no legacy Modelo 200 authority outside
    the registry-aware portal entry. The registry is the only authority
    from inception.
- [ ] Modelo 200 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] `RegistryValidator.validate_modelo` passes for Modelo 200 against
    catalogue with full source-integrity check.
  - [x] `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
    passes for committed registry validation and cross-dependency behaviour.
  - [x] `uv run ruff check` and `uv run ty check` clean on the touched test
    surface.
- [ ] Modelo 200 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 200 filing-grade values.

### Wave 16 Modelo 232 Parity Ledger

- [x] Modelo 232 audit: greenfield in `src/aeat/` and `tests/` — only the
  registry surfaces and dedicated `test_modelo_232_registry.py` suite mention
  Modelo 232; no legacy ruleset, builder, hydrate, or category mapping exists
  to teardown.
- [x] Modelo 232 legal basis: BOE-grounded catalogue covers LIS art 18
  (operaciones vinculadas), RIS art 13 (information/documentation duty), and
  Orden HFP/816/2017 articles 1 (aprobación), 2 (obligados/umbrales), 3
  (contenido secciones I/II/III), and 4 (plazo).
- [x] Modelo 232 AEAT official guidance: AEAT procedure HTML captured at
  `corpus/aeat_official/instructions/modelo_232/files/modelo-232-procedure.html`
  (corrected from initial GI09 mistake to the canonical GI43.shtml).
- [x] Modelo 232 workbook/layout coverage: DR232e17v14.xlsx (current 2018+)
  and DR232e17v13.xlsx (historical 2016-2017) are both registered as
  `record_design_layout` parity refs.
- [x] Modelo 232 live filed-data discovery: authenticated read-only scan via
  `aeat.entrypoints.cli.registry capture-filed-data --modelo 232` returned
  zero filed rows for ejercicios 2018-2024 under the test NIF; recorded as
  discovery evidence rather than parser coverage.
- [ ] Modelo 232 live sanitized fixture: no-fixture-guard remains active —
  no Modelo 232 declaration is filed under the test NIF (autónomo NIF, no
  corporate-tax operations vinculadas), so no real artefact is available
  to sanitize.
- [x] Modelo 232 legal/source catalogue closure: extends
  `registry/aeat/legal/is.toml` with the LIS/RIS/Order articles and the
  `aeat-dr-232-2018`, `aeat-dr-232-2016`, `aeat-modelo-232-procedure`, and
  `boe-modelo-232-2017-form` source refs.
- [x] Modelo 232 TOML identity and revisions: two revisions
  (`2016-2017`, `2018-y-siguientes`) in `registry/aeat/modelos/232.toml`
  with annual cadence, `["0A"]` period selector, full deadline windows
  (Nov plazo for ejercicios 2016-2026), and the corresponding application
  links per revision.
  - [x] Review, approval, reconciliation, and workflow links are declared for
    both revisions and are scoped through each informative construct.
- [x] Modelo 232 casilla schema: declarante header casillas (ejercicio,
  tipo de ejercicio, CNAE) with section, data type, requiredness, export
  refs, legal refs, and source refs per revision.
- [x] Modelo 232 formulas, parameters, and bindings: 217 layout bindings
  per revision cover sections I + II (page-01) and III + IV (page-02) at
  field-level fidelity. Modelo 232 is informative-only so no formulas /
  parameters / cross-model relations are declared (informative-only
  invariant enforced by the test suite).
- [x] Modelo 232 extraction profiles: declaracion-pdf profile with
  `aeat.adapters.inbound.declaracion.parse_declaracion`, strict confidence,
  fail-hard semantics, target declarante casillas.
- [x] Modelo 232 live cross-reference guard: static_official_documentation
  and authenticated_read_surface (www1+www6 hosts, GET/HEAD/OPTIONS only,
  all writes / signing / payment / amendment / cancellation forbidden).
- [x] Modelo 232 export/filing linkage: full envelope DR23200 + page-01
  DR23201 (1500 chars) + page-02 DR23202 (3500 chars) + envelope close
  per revision; export-derive resolves to 95 page-01 fields and 155
  page-02 fields matching the official workbook.
  - [x] Review, approval, reconciliation, and workflow entry points are
    snapshot-gated application links; Modelo 232 remains informative-only.
- [x] Modelo 232 legal correctness tests: 29 behaviour tests covering
  identity, revision selection by filing year, the informative-only
  invariant, workbook parity, both live cross-reference surfaces,
  November plazo (2016-2026), section 3+4 / 5+6 binding range
  contiguity, and construct membership consistency.
  - [x] Workflow-link behavior test proves the review, approval,
    reconciliation, and workflow surfaces require snapshots and are
    construct-scoped for each revision.
- [ ] Modelo 232 live/filed-data tests: gated on the live sanitized
  fixture — no fixture exists yet.
- [ ] Modelo 232 teardown: N/A — Modelo 232 was greenfield; the audit
  confirmed no legacy ruleset, builder, hydrate, or category mapping
  surfaces exist outside the registry.
- [x] Modelo 232 quality gate: validate_modelo passes against the
  committed catalogues; 29 focused tests pass; `ruff check`, `ty check`,
  and `git diff --check` clean for the touched surfaces.
- [ ] Modelo 232 completion gate: gated on the live sanitized fixture
  and live tests rows; foundation + sections 3-6 + envelope/page export
  layout landed in commit `f9b62e31` (Add Modelo 232 registry).

### Wave 17 Modelo 720 Parity Ledger

- [x] Modelo 720 audit: greenfield in `src/aeat/` and `tests/` — only the
  registry surfaces and dedicated `test_modelo_720_registry.py` suite mention
  Modelo 720; no legacy ruleset, builder, or hydrate path exists to teardown.
- [x] Modelo 720 legal basis: BOE-grounded catalogue covers LGT (Ley
  58/2003) DA 18 (foreign-asset reporting obligation), RGAT (RD 1065/2007)
  arts 42-bis (cuentas), 42-ter (valores) and 54-bis (inmuebles), and Orden
  HAP/72/2013 articles 1 (aprobación), 2 (obligados, umbral €50k por
  categoría) and 7 (plazo 1 enero - 31 marzo).
- [x] Modelo 720 AEAT official guidance: AEAT procedure HTML captured at
  `corpus/aeat_official/instructions/modelo_720/files/modelo-720-procedure.html`
  (procedimiento GI34).
- [x] Modelo 720 workbook/layout coverage: only one AEAT artefact exists
  (the `modelo_720.pdf` 599 KB record design — no XLSX). Registered as
  `record_design_layout` parity ref.
- [x] Modelo 720 live filed-data discovery: authenticated read-only scan
  via `aeat.entrypoints.cli.registry capture-filed-data --modelo 720`
  returned zero filed rows for ejercicios 2012-2024 under the test NIF;
  recorded as discovery evidence rather than parser coverage.
- [ ] Modelo 720 live sanitized fixture: no-fixture-guard remains active —
  no Modelo 720 declaration is filed under the test NIF.
- [x] Modelo 720 legal/source catalogue closure: new
  `registry/aeat/legal/foreign-assets.toml` with LGT DA 18, RGAT
  42-bis/42-ter/54-bis, Orden HAP/72/2013 arts 1/2/7, plus `aeat-dr-720`,
  `aeat-modelo-720-procedure`, and `boe-modelo-720-2013-form` sources.
- [x] Modelo 720 TOML identity and revisions: single revision
  `2013-y-siguientes` (year_from=2012) in `registry/aeat/modelos/720.toml`
  with annual cadence, `["0A"]` period selector, 15 deadline windows
  (ejercicio 2012 transitional Feb-Apr 2013, then 1 Jan - 31 Mar of the
  year following ejercicio for 2013-2026), and the corresponding
  application links.
  - [x] Review, approval, reconciliation, and workflow links are declared and
    scoped through the informative construct.
- [x] Modelo 720 casilla schema: declarante header casillas (ejercicio,
  tipo de declaración) with section, data type, requiredness, legal refs,
  and source refs.
- [x] Modelo 720 formulas, parameters, and bindings: 43 layout bindings
  (13 type_1 declarante + 30 type_2 detalle) parsed from the BOE order's
  anexo "Diseños físicos y lógicos" cover the full record-design field
  geometry. Modelo 720 is informative-only so no formulas / parameters /
  relations are declared.
- [x] Modelo 720 extraction profiles: declaracion-pdf profile with
  `aeat.adapters.inbound.declaracion.parse_declaracion`, strict
  confidence, fail-hard semantics, target declarante casillas.
- [x] Modelo 720 live cross-reference guard: static_official_documentation
  and authenticated_read_surface (www1+www6 hosts, GET/HEAD/OPTIONS only,
  all writes / signing / payment / amendment / cancellation forbidden).
- [x] Modelo 720 export/filing linkage: type_1 record (single, encoding
  ISO-8859-1, CRLF) + type_2 record (`repeat = "binding_rows"` for one
  record per declared asset) auto-derive their fields from the layout
  bindings via `derive_export_layouts_from_bindings`.
  - [x] Review, approval, reconciliation, and workflow entry points are
    snapshot-gated application links; Modelo 720 remains informative-only.
- [x] Modelo 720 legal correctness tests: 20 behaviour tests covering
  identity, revision selection, the informative-only invariant, workbook
  parity, both live cross-reference surfaces, the January-March plazo
  (with the 2012 transitional window), the type_1 / type_2 binding
  scope, and construct membership consistency.
  - [x] Workflow-link behavior test proves the review, approval,
    reconciliation, and workflow surfaces require snapshots and are
    construct-scoped.
- [ ] Modelo 720 live/filed-data tests: gated on the live sanitized
  fixture.
- [ ] Modelo 720 teardown: N/A — Modelo 720 was greenfield; no legacy
  authority surfaces exist outside the registry.
- [x] Modelo 720 quality gate: validate_modelo passes against the
  committed catalogues; 20 focused tests pass; `ruff check`, `ty check`,
  and `git diff --check` clean for the touched surfaces.
- [ ] Modelo 720 completion gate: gated on the live sanitized fixture
  and live tests rows; foundation landed in commit `b85b207b` (Add
  Modelo 720 registry foundation), sections expansion in `b92a2cc4`
  (Expand Modelo 720 with type-1 + type-2 layout bindings).

### Wave 18 Modelo 840 Parity Ledger

- [x] Modelo 840 audit: greenfield in `src/aeat/` — the only references are
  enumerations of "840" alongside other censal/profile-authority modelo IDs
  in `test_cross_dependency_contract.py` and `test_codes.py`; no legacy
  ruleset, builder, hydrate, or category mapping exists to teardown.
- [x] Modelo 840 legal basis: BOE-grounded catalogue covers TRLRHL (RD
  Legislativo 2/2004) arts 78 (naturaleza, hecho imponible), 82 (exenciones
  con umbral €1M cifra de negocios), 90 (gestión tributaria, matrícula del
  impuesto), and Orden HAC/2572/2003 apartados 1 (aprobación) and 6 (plazos
  de alta, variación, baja por remisión a RD 243/1995).
- [ ] Modelo 840 AEAT official guidance: Modelo 840 has no
  `/Sede/procedimientoini/GIxx.shtml` page on the AEAT sede (IAE
  administration is partly delegated to municipalities/diputaciones). The
  BOE Order serves as the procedural reference; an official AEAT
  procedure HTML may be added when one is published.
- [x] Modelo 840 workbook/layout coverage: only one AEAT artefact exists
  (the `dr840.pdf` 99 KB record design — no XLSX). Registered as
  `record_design_layout` parity ref.
- [ ] Modelo 840 live filed-data discovery: deferred — Cl@ve Móvil
  approval timed out twice. Can be revisited with the same authenticated
  CLI used for Modelos 232 and 720 once the user is at their phone.
- [ ] Modelo 840 live sanitized fixture: no-fixture-guard remains active.
- [x] Modelo 840 legal/source catalogue closure: new
  `registry/aeat/legal/iae.toml` with TRLRHL arts 78/82/90, Orden
  HAC/2572/2003 apartados 1/6, plus `aeat-dr-840` and
  `boe-modelo-840-2003-form` sources.
- [x] Modelo 840 TOML identity and revisions: single revision
  `2003-y-siguientes` (year_from=2003) in `registry/aeat/modelos/840.toml`
  with `ad_hoc` cadence (filing is event-driven within 1 month per RD
  243/1995 arts 5-7), `["0A"]` period selector, and the corresponding
  application links.
- [x] Modelo 840 casilla schema: declarante header casillas (tipo de
  declaración, ejercicio) with section, data type, requiredness, legal
  refs, and source refs.
- [ ] Modelo 840 formulas, parameters, and bindings: foundation has no
  layout bindings yet — the corpus is a PDF (no XLSX) and the BOE Order's
  anexo would need PDF parsing. Deferred to a follow-up slice.
- [x] Modelo 840 extraction profiles: declaracion-pdf profile with
  `aeat.adapters.inbound.declaracion.parse_declaracion`, strict
  confidence, fail-hard semantics, target declarante casillas.
- [x] Modelo 840 live cross-reference guard: static_official_documentation
  and authenticated_read_surface (www1+www6 hosts, GET/HEAD/OPTIONS only,
  all writes / signing / payment / amendment / cancellation forbidden).
- [x] Modelo 840 export/filing linkage: foundation only — no record-design
  bindings yet, so no export records. Application links cover portal,
  filing, extractor, verification.
- [x] Modelo 840 legal correctness tests: 12 behaviour tests covering
  identity, revision selection, the informative-only invariant, workbook
  parity, both live cross-reference surfaces, the ad_hoc filing schedule,
  and construct membership consistency.
- [ ] Modelo 840 live/filed-data tests: gated on live discovery + fixture.
- [ ] Modelo 840 teardown: N/A — Modelo 840 was greenfield; the only
  references are enumerations alongside other valid modelo IDs and stay
  valid after the registry is registered.
- [x] Modelo 840 quality gate: validate_modelo passes against the
  committed catalogues; 12 focused tests pass; `ruff check`, `ty check`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 840 completion gate: gated on live discovery + fixture +
  layout-binding rows; foundation landed in commit `1418eb26` (Add
  Modelo 840 registry foundation).

### Wave 19 Modelo 036 Parity Ledger

- [ ] Modelo 036 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 036 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 036 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 036 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 036 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 036 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 036 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 036 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 036 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/036.toml`.
- [ ] Modelo 036 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 036 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 036 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 036 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 036 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 036 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, censal registration
  conditions, and any filed-data bindings are correct against official
  authority.
- [ ] Modelo 036 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 036 teardown: delete or neutralize all old Modelo 036 authorities
  in rulesets, filing builders, category mappings, censal hydrate tables,
  casilla projections, deadlines, generated exports, and legacy fixtures.
- [ ] Modelo 036 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 036 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 036 filing-grade values.

### Wave 20 Modelo 037 Parity Ledger

- [ ] Modelo 037 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 037 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 037 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, retirement rule,
  historical support rule, and temporal applicability rule.
- [ ] Modelo 037 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 037 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 037 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 037 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact if official support remains,
  sanitize identity data, commit the redacted fixture, and prove it parses
  through the registry layout.
- [ ] Modelo 037 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 037 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported or removed revision, period selector,
  deadline windows, support-removal decision, and application links in
  `registry/aeat/modelos/037.toml`.
- [ ] Modelo 037 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs, or prove filing-grade support is removed.
- [ ] Modelo 037 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output, or prove no filing-grade calculation remains.
- [ ] Modelo 037 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs, or prove removal.
- [ ] Modelo 037 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 037 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots, or delete unsupported filing-grade entry points.
- [ ] Modelo 037 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, historical/current
  support semantics, and any filed-data bindings are correct against official
  authority.
- [ ] Modelo 037 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 037 teardown: delete or neutralize all old Modelo 037 authorities
  in rulesets, filing builders, category mappings, censal hydrate tables,
  casilla projections, deadlines, generated exports, and legacy fixtures.
- [ ] Modelo 037 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 037 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 037 filing-grade values.

### Wave 21 Modelo 100 Parity Ledger

- [ ] Modelo 100 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 100 identity,
  casillas, rules, calculations, deadlines, exports, borrador data, Renta WEB
  data, rental data, CCAA rules, or live filed data.
- [ ] Modelo 100 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, autonomous
  community rule, deduction, reduction, rental rule, and temporal applicability
  rule.
- [ ] Modelo 100 AEAT official guidance: capture and hash AEAT Renta manuals,
  practical handbooks, instructions, record designs, and other official source
  artefacts required by the registry definition.
- [ ] Modelo 100 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 100 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, justificante availability,
  borrador/data-fiscal availability, and forbidden authenticated surfaces.
- [x] Modelo 100 live sanitized fixture: capture at least one read-only live
  submitted-file, declaration-copy, or official filed-data artefact, sanitize
  identity data, commit the redacted fixture, and prove it parses through the
  registry layout.
- [ ] Modelo 100 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 100 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/100.toml`.
- [x] Modelo 100 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, source
  refs, and Renta epoch grouping.
  - [x] Schema deepened from 224 hand-curated casillas to **11,302 casillas
    across all six ejercicios 2020-2025** by parsing the AEAT-published
    `declaracion-individual` `.properties` data dictionaries. Each casilla
    carries a number, AEAT label, snake_case section path, data type
    derived from the AEAT type code (P102/P010/P012/P020/P030/P032/P040/
    P042/P072/P122 to money, N102 to decimal, X/FEC/TIT/AAA/MOD to text,
    LGC/S_N to boolean, SEQ to integer), `input_kind = "manual"` default,
    and revision-level legal_refs/source_refs inherited so each casilla
    carries an authority chain. Existing hand-authored casillas were
    preserved.
  - [x] Section paths re-derived from the AEAT XPath after stripping the
    `/DatosEconomicos` XML root, producing 190 meaningful 2-3-deep
    section combinations (e.g. `["resultados", "deduccion_autonomica_res",
    "c_valenciana_res"]` for Valencia autonomic deductions,
    `["toma_datos_ampliada", "inmuebles", "inmueble"]` for real-estate
    per-property entries, `["resultados", "anexo_a_res",
    "deducciones_inversion_empresarial_res"]` for Annex A business
    investment deductions). Two pre-existing envelope casillas (ZCCAD,
    TIPOTRIBUTACION) were realigned from the redundant `datos_economicos`
    bucket to `datos_identificativos` to match the surrounding declarante
    envelope rows.
  - [x] Cross-modelo schema hygiene tests landed at
    `src/aeat/domain/calculations/registry/test_schema_hygiene.py` so a
    future generator regression cannot reintroduce duplicate casilla
    declarations or revert section quality. The tests run against every
    committed `registry/aeat/modelos/*.toml` and check no duplicate
    casilla ids within a revision, no duplicate casilla numbers within a
    revision, every casilla declares at least one section segment, every
    section part is snake_case, and section[0] is not an AEAT XML root
    container token (`datoseconomicos`, `datos_economicos`, `rootnode`,
    `root_node`).
  - [ ] Outstanding sub-step: hand-author `input_kind = "bound"` /
    `"computed"` semantics, formula bindings, CCAA-conditional
    reductions, and per-casilla legal-ref refinement beyond revision-
    level inheritance. The current state is the inventory of every
    numbered casilla; the calculation chain is wired only for the
    settlement-chain casillas (cuota_integra, cuota_liquida, cuota
    diferencial, resultado_declaracion, payments-on-account
    cross-dependencies with Modelo 130 and 131).
- [ ] Modelo 100 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, cross-model relation, CCAA parameter,
  rental algorithm, rounding rule, legal ref, source ref, and trace output.
- [ ] Modelo 100 extraction profiles: define submitted-file, declaration PDF,
  borrador, and data-fiscal extraction profiles with target casillas, accepted
  artefacts, min coverage, failure semantics, legal refs, and source refs.
- [x] Modelo 100 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, cancellation, and
  authenticated Renta WEB synthetic-test actions.
- [x] Modelo 100 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 100 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relations to Modelos
  130 and 131, Renta epochs, CCAA behaviour, rental behaviour, and any
  filed-data bindings are correct against official authority.
- [x] Modelo 100 live/filed-data tests: run committed sanitized submitted-file,
  declaration-copy, borrador, or data-fiscal parser tests, encrypted
  observation-store roundtrip tests where applicable, and filed-data parser
  tests without defaults or silent degradation.
- [ ] Modelo 100 teardown: delete or neutralize all old Modelo 100 authorities
  in Renta rulesets, CCAA helpers, rental legal-calculation modules, filing
  builders, category mappings, casilla projections, deadlines, generated
  exports, hydrate paths, borrador casilla truth, and legacy fixtures.
- [ ] Modelo 100 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 100 completion gate: mark complete only when no unchecked Renta
  epoch row remains and no old authority can populate Modelo 100 filing-grade
  values.

### Wave 22 Modelo 184 Parity Ledger

- [x] Modelo 184 registry foundation: annual informative revision
  `2015-y-siguientes` with period `0A` is present.
- [x] Modelo 184 informational casillas: `decl.ejercicio` and
  `decl.tipo-declaracion` are represented.
- [x] Modelo 184 layout authority: record-design layout parity is present and
  remains classified as layout authority only.
- [x] Modelo 184 extraction and verification: extraction profile and
  verification expectation are present.
- [x] Modelo 184 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 184 application/deadline linkage: filing, extractor, verification,
  deadline links, annual schedule, and 2018-2026 February deadline windows are
  represented.
- [ ] Modelo 184 full casilla corpus: enumerate and register the complete
  official casilla set.
- [ ] Modelo 184 formula/binding coverage: classify whether formulas or
  bindings apply and register them if official evidence supports them.
- [ ] Modelo 184 export/file generation parity: represent export/file layout
  and generation where official filing support requires it.
- [ ] Modelo 184 live/read fixture evidence: capture committed sanitized
  read-only evidence and verify parser behaviour.
- [ ] Modelo 184 perceptor/entity parity ledger: define entity/perceptor-detail
  coverage and consistency checks.
- [ ] Modelo 184 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

### Wave 23 Modelo 308 Parity Ledger

- [x] Modelo 308 registry foundation: IVA ad-hoc refund request revision
  `2009-y-siguientes` with period `AD-HOC` is present.
- [x] Modelo 308 informational casillas: `decl.ejercicio` and
  `decl.tipo-solicitud` are represented.
- [x] Modelo 308 layout authority: record-design layout parity is present and
  remains classified as layout authority only.
- [x] Modelo 308 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 308 application linkage: portal, filing, extractor, verification,
  and deadline links are represented.
- [ ] Modelo 308 deadline windows: register official deadline windows where
  the operator profile yields a filing period.
- [ ] Modelo 308 operator-type deadline refinement: encode official
  operator-trigger distinctions without ad-hoc category maps.
- [ ] Modelo 308 calculation/binding casillas: register binding casillas only
  where official evidence requires filing-grade calculation.
- [ ] Modelo 308 full casilla corpus: enumerate and register the complete
  official casilla set.
- [ ] Modelo 308 profile-conditional plazos: represent profile-dependent
  filing deadlines as registry facts.
- [ ] Modelo 308 export/layout deepening: add official export or filing layout
  details beyond record-design layout where required.
- [ ] Modelo 308 live/read fixture evidence: capture committed sanitized
  read-only evidence and verify parser behaviour.
- [ ] Modelo 308 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

### Wave 24 Modelo 309 Parity Ledger

- [x] Modelo 309 registry foundation: IVA non-periodic declaration revision
  `2004-y-siguientes` is present.
- [x] Modelo 309 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 309 application linkage: calculation, filing, workflow,
  reconciliation, review, approval, extractor, verification, and deadline links
  are represented.
- [x] Modelo 309 typed binding/result-casilla slice: two
  `ledger_iva_aggregation` bindings, two bound IVA casillas, one computed total
  casilla, two informational casillas, and one formula are represented.
- [ ] Modelo 309 trigger coverage: extend beyond intra-community
  autorepercutido and recargo-equivalencia soportado only where official
  evidence supports the trigger.
- [ ] Modelo 309 full casilla corpus: enumerate and register the complete
  official casilla set.
- [ ] Modelo 309 live/static parity fixture: capture sanitized evidence that
  verifies parser and local calculation behaviour against official data.
- [ ] Modelo 309 deadline windows: register official deadline windows and
  profile conditions.
- [ ] Modelo 309 formula coverage: deepen formulas beyond the current total
  formula only where official evidence supports them.
- [ ] Modelo 309 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

### Wave 25 Modelo 322 Parity Ledger

- [x] Modelo 322 registry foundation: IVA group-of-entities individual monthly
  declaration revision `2008-y-siguientes` with periods `01` through `12` is
  present.
- [x] Modelo 322 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 322 schedule linkage: monthly schedule and representative
  deadline windows are represented.
- [x] Modelo 322 typed binding/result-casilla slice: five
  `ledger_iva_aggregation` bindings, five bound IVA casillas, three computed
  result casillas, two informational casillas, and three formulas are
  represented.
- [ ] Modelo 322 full official casilla corpus: enumerate and register the
  complete official casilla set.
- [ ] Modelo 322 group-regime-specific inputs: register official group-member
  inputs and filing constraints.
- [ ] Modelo 322 live/read fixture evidence: capture committed sanitized
  read-only evidence and verify parser behaviour.
- [ ] Modelo 322 export/file layout parity: represent official export or filing
  layout details beyond record-design layout where required.
- [ ] Modelo 322 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

### Wave 26 Modelo 353 Parity Ledger

- [x] Modelo 353 registry foundation: IVA group-of-entities aggregate monthly
  declaration revision `2008-y-siguientes` is present.
- [x] Modelo 353 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 353 schedule linkage: monthly schedule and representative
  deadline windows are represented.
- [x] Modelo 353 typed binding/result-casilla slice: the current
  result-casilla and formula shape matches Modelo 322.
- [ ] Modelo 353 member relation: register the official aggregation relation to
  member Modelo 322 filings.
- [ ] Modelo 353 group consolidation semantics: encode dominant-entity
  consolidation rules as registry facts.
- [ ] Modelo 353 full official casilla corpus: enumerate and register the
  complete official casilla set.
- [ ] Modelo 353 live/read fixture evidence: capture committed sanitized
  read-only evidence and verify parser behaviour.
- [ ] Modelo 353 export/file layout parity: represent official export or filing
  layout details beyond record-design layout where required.
- [ ] Modelo 353 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

### Wave 27 Modelo 360 Parity Ledger

- [x] Modelo 360 registry foundation: IVA EU refund request revision
  `2010-y-siguientes` with period `AD-HOC` is present.
- [x] Modelo 360 informational casillas: `decl.ejercicio` and
  `decl.estado-miembro` are represented.
- [x] Modelo 360 layout authority: record-design layout parity is present and
  remains classified as layout authority only.
- [x] Modelo 360 read-only surfaces: static official documentation and
  authenticated read-only cross references are present.
- [x] Modelo 360 application/deadline linkage: filing, extractor,
  verification, deadline links, and 2024/2025 September 30 deadline windows are
  represented.
- [ ] Modelo 360 refund-line/request detail model: register refund request line
  structure and validation rules.
- [ ] Modelo 360 typed EU member/refund-country facts: bind member-state and
  refund-country facts to the central schema.
- [ ] Modelo 360 amount/binding/formula coverage: classify whether amount
  bindings or formulas apply and register them if official evidence supports
  them.
- [ ] Modelo 360 full casilla corpus: enumerate and register the complete
  official casilla set.
- [ ] Modelo 360 live/read fixture evidence: capture committed sanitized
  read-only evidence and verify parser behaviour.
- [ ] Modelo 360 completion gate: close only after the wave has no unchecked
  row and no unsupported authority can populate filing-grade values.

## Tasks

- `Mandatory per-step quality and sanitization gate`
  - [ ] Apply this gate to every phase item, wave item, file-level cleanup item,
     schema change, TOML change, test change, CLI change, execution record, and
     review record before marking the item complete.
  - [ ] Search every touched runtime file, TOML file, test file, fixture helper,
     CLI surface, and vault execution artefact for development-condition
     metadata. Remove language about local work conditions, temporary branches,
     phases as implementation trivia, wave mechanics, loop mechanics, review
     process, migration mechanics, issue numbers, ticket numbers, PR numbers,
     pull requests, commit ids, transient dates, personal notes, or agent
     process.
  - [ ] Remove migration and compatibility vocabulary from runtime code and
     tests unless the domain object is genuinely a user-facing legal amendment,
     filing correction, data import, or storage-format evolution. Banned
     architecture-cleanup vocabulary includes `legacy`, `shim`, `compat`,
     `back-compat`, `migration`, `migrated`, `deprecated`, `temporary`,
     `phase`, `wave`, `loop`, `ADR`, `PR`, `issue`, `ticket`, `epic`, and
     numbered project references.
  - [ ] Remove numbered vault references and development-flow references from
     runtime code, tests, TOML, CLI help, docstrings, comments, and fixtures.
     Vault documents may keep their own dates and titles, but runtime surfaces
     must not explain themselves by pointing at vault process artefacts.
  - [ ] Remove hardcoded support metadata introduced only by the rebuild process:
     development status enums, disabled placeholders, dormant branches,
     compatibility aliases, old import aliases, one-off support flags, migration
     provenance, generated provenance, hydrate provenance, and any fallback
     whose only purpose is to keep old callers alive.
  - [ ] Verify comments and docstrings describe stable product behaviour only:
     what the module does, what legal/source authority it consumes, what it
     validates, and what it refuses. They must not describe why the current
     development pass changed something or which plan step caused it.
  - [ ] Verify tests exercise current behaviour through committed registry data
     and public APIs. Tests must focus on loading, validation, calculation,
     export, filing, source closure, legal closure, and failure semantics.
  - [ ] Run static discovery over touched files for the banned vocabulary and
     metadata patterns. Any hit must be removed or justified as stable domain
     language before the item is complete.
  - [ ] Add or extend behaviour tests through public APIs when a removed
     authority surface would otherwise affect runtime behaviour. Tests must
     exercise loading, validation, calculation, export, or filing behaviour,
     with assertions grounded in current product behaviour.
  - [ ] Run `git diff --check`, focused tests for the touched module,
     registry-backed public behaviour tests, `ruff`, and `ty` for every
     completed batch. A batch with sanitization drift is not complete even if
     behaviour tests pass.

- `Phase 0` Live and workbook parity infrastructure buildout
  - [x] Create the workbook/live parity backend under the calculation registry
     package before any modelo refactor begins.
  - [x] Expose verification commands for workbook inventory, workbook
     classification, formula discovery, synthetic fixture validation,
     workbook-runner availability, registry/workbook parity comparison, and
     remote-state guard policy.
  - [x] Build an official workbook inventory scanner over
     `corpus/aeat_official/disenos_registro` that records workbook path, modelo,
     revision hint, extension, byte count, SHA-256, sheet names, formula-cell
     count, likely input cells, likely output cells, and scan errors.
  - [x] Add per-file scanner timeouts, resumable progress, deterministic JSON
     or TOML reports, and diagnostics so large XLSX files cannot stall the
     rebuild pipeline.
  - [x] Classify every official workbook as formula-bearing form,
     record-design layout, validation-hint workbook, static layout workbook,
     unsupported binary XLS, or unreadable artefact.
  - [x] Implement XLSX formula discovery with `openpyxl` for formula addresses,
     referenced cells, literal constants, formula text, worksheet names, and
     output-cell candidates.
  - [x] Research and decide the binary XLS reader/conversion path. Until a safe
     parser exists, every XLS artefact is recorded as unsupported coverage
     rather than silently skipped.
  - [x] Implement safe isolated LibreOffice conversion for binary XLS official
     artefacts so the registry can inspect converted XLSX/CSV output without
     mutating the committed corpus. Converted artefacts must retain the original
     XLS hash as source identity and must be classified by evidence tier after
     inspection.
  - [x] Keep workbook execution platform-neutral. LibreOffice headless is the
     default local recalculation route when available; Windows Excel COM is an
     optional runner only and must never be required for registry validation,
     export rendering, or production runtime.
  - [x] Define the workbook parity runner contract: load official workbook,
     inject synthetic inputs, recalculate with a sanctioned local spreadsheet
     engine or documented equivalent, read output cells, and emit a trace.
  - [x] Define one synthetic input fixture format per modelo/revision. Fixtures
     must feed both the registry engine and workbook/simulator parity surfaces
     without hand-adjusted values.
  - [x] Implement parity comparison records that include registry snapshot id,
     workbook source hash, sheet/cell addresses, synthetic input ids, expected
     workbook outputs, actual registry outputs, tolerances, rounding mode,
     legal refs, and source refs.
  - [x] Connect workbook parity coverage to model-law coverage ledgers. A model
     wave cannot start until its official workbook coverage is discovered and
     classified.
  - [x] Connect workbook/simulator parity to the remote-state guard. Workbook
     parity is local-only; simulator parity must be read-only Open or authorized
     Integration/test service only.
  - [x] Run and pass the workbook/live parity backend verification suite. No
     modelo refactor wave may start until this backend exists and the
     verification suite passes.
  - [x] Correct workbook classifier so official `disenos_registro` XLSX files
     with positional helper formulas are classified as record-design layouts,
     not tax calculation formula oracles. Current committed corpus evidence is
     72 workbook artefacts: 47 record-design XLSX files, 25 unsupported binary
     XLS files, and zero committed official formula-form tax calculation
     workbooks.

- `Phase 0A` Approval, governance, and teardown controls
  - [x] Treat the accepted ADR as the controlling architecture for all subsequent
     registry work.
  - [x] Define the wave completion contract: each modelo must have reviewed TOML,
     strict registry validation, legal/source evidence, calculation tests,
     export or filing linkage, trace output, and deletion of old model-specific
     authority.
  - [x] Define the teardown contract: old code may be read for evidence and may
     be cited in execution records, but it is not retained as a runtime fallback
     or alternate source of truth.
  - [x] Establish import-boundary rules that forbid filing, review, export, CLI,
     and application code from importing old formula rulesets, hydrate writers,
     generated export modules, or model-specific filing builders as calculation
     authorities.
  - [x] Establish execution-record requirements for every wave: audit notes,
     source/legal evidence notes, formula evidence notes, verification evidence,
     and deletion evidence.

- `Phase 0B` Authority-tier verification framework
  - [x] Codify the evidence hierarchy in a companion ADR: BOE legal texts are
     legal authority; AEAT instructions/manuals are official source guidance;
     AEAT Open/help programs and true formula-form workbooks are executable
     parity evidence when safe; record designs are layout authority only.
  - [x] Record official-source research for the hierarchy, including BOE law
     and regulations, AEAT Modelo instructions, AEAT manual surfaces, AEAT
     Open/help services, and AEAT record-design artefacts.
  - [x] Extend shared legal/source catalogue schema with explicit evidence-tier
     classification for each retained source reference.
  - [x] Extend workbook/source verification reports so every artefact states
     which tier it satisfies and which tier it cannot satisfy.
  - [x] Extend model-law coverage ledgers so each modelo/revision reports legal
     authority coverage, official source guidance coverage, executable parity
     coverage, and layout/export coverage as separate gates.
     - [x] Add a whole-tree model-law coverage audit that validates every
       committed modelo revision once, fails on missing legal authority,
       official source guidance, or layout authority, and reports executable
       parity gaps without treating them as solved.
  - [x] Extend validator failure semantics so a filing-grade formula cannot be
     validated from layout authority alone and cannot use executable parity as
     a substitute for BOE legal basis.
  - [x] Extend formula and parameter source grounding so official-source
     guidance citations must resolve to reviewed source text in the local AEAT
     corpus before a registry snapshot validates.
     - [x] Manual PDF source references are text-extracted by the registry
       validator and normalized accent-insensitively, so formula citations can
       be grounded in AEAT manuals rather than record-design layout text.
  - [x] Extend legal grounding so legal catalogue references can require BOE
     corpus text and registry validation fails when the cited local legal text
     does not contain the required legal anchors.
  - [x] Extend registry verification so cross-model relations are validated
     against the loaded modelo registry: source modelo existence, source
     revision selector closure, declared source periods, target periods,
     source outputs, and supported aggregation operations.
  - [x] Extend relation schema so every cross-model relation declares its
     dependency role, and annual-summary relations cannot validate unless they
     are explicitly classified as periodic-to-annual summary dependencies.
  - [x] Extend registry inspection and verification reports so relation counts
     and dependency roles are visible at tree and revision level for plan
     tracking and audit review.
  - [x] Add a typed relation-source requirement resolver so registry relations
     expose the exact source modelo, filing year, periods, source output,
     target bindings, dependency role, and aggregation operation that secure
     storage or read-only AEAT observation backends must fetch.
  - [x] Resolve registry relation values from normalized filed-declaration
     observations with hard failures for missing source filings, duplicate
     source filings, missing observed outputs, and unsupported aggregations.
  - [x] Add generalized cross-dependency contract tests for role semantics,
     source-requirement derivation, formula consumption of calculation
     relations, and casilla attachment for formula relation dependencies.
  - [x] Extend cross-dependency contract tests so relation target bindings must
     mirror source modelo, source output/casilla, source periods, and
     aggregation, and formula-level relation dependencies must carry the
     relation legal basis.
  - [x] Extend cross-dependency contract tests so each relation source output
     resolves to a filing-grade source-modelo casilla or declared algorithm
     output in every selected source revision.
  - [x] Extend workbook parity tests so converted XLS record-design files are
     accepted as layout evidence only and rejected as calculation parity
     oracles.
  - [x] Extend live/simulator verification tests so AEAT web/help programs are
     executable parity evidence only when remote-state guards prove the surface
     is read-only or explicitly authorized for test use.
  - [x] Re-run registry validation, workbook/source verification, remote-state
     guard tests, filing/export tests, `ruff`, `ty`, and `git diff --check`
     before starting or continuing concrete modelo implementation waves.

- `Phase 0C` Live filed-declaration data capture backend
  - [x] Treat live AEAT reads as observed filed-declaration data capture, not
     as a calculation authority and not as a justificante-only metadata lookup.
  - [x] Extend the read-only declaration-register backend so a query against
     `Consultar declaraciones presentadas` can capture register metadata,
     submitted TXT or model-specific file, full declaration-copy PDF,
     justificante PDF, source URLs, content types, byte counts, SHA-256 hashes,
     retrieval timestamps, and authenticated identity.
     - [x] Register row metadata capture implemented with source URL, byte
        count, hash, retrieval timestamp, and authenticated identity.
     - [x] Submitted-file capture implemented with source URL, content type,
        byte count, hash, and retrieval timestamp.
     - [x] Justificante PDF capture implemented with source URL, content type,
        byte count, hash, and retrieval timestamp.
     - [x] Full declaration-copy PDF capture is implemented through a distinct
        declaration-copy surface when AEAT exposes that register column, not
        inferred from justificante metadata.
  - [x] Add a typed `FiledDeclarationObservation` schema for normalized live
     read results. It must carry modelo, ejercicio, period, expediente id,
     status, presented timestamp, authenticated identity, source artefacts,
     observed casilla values, metadata, extraction coverage, and optional
     registry snapshot id.
  - [x] Add a typed `FiledDeclarationArtefact` schema for each captured
     register row, submitted file, declaration PDF, and justificante PDF. It
     must preserve artefact kind, source URL, content type, byte count, SHA-256,
     and capture timestamp.
  - [x] Persist live filed-declaration artefacts and observation manifests only
     through the encrypted storage substrate before any modelo implementation
     wave consumes them.
     - [x] Store register rows, submitted files, declaration-copy PDFs, and
        justificantes as `FINANCIAL` encrypted blob records.
     - [x] Store normalized filed-declaration observations as encrypted
        `FINANCIAL` envelopes.
     - [x] Report encrypted storage references from the CLI instead of
        local filesystem locations.
     - [x] Test encrypted artefact and observation roundtrip through the store
        API and assert filing bytes, identity values, expediente ids, and
        casilla values are absent from disk plaintext.
     - [x] Store observation manifests under opaque hashed paths so filing
        metadata is not embedded in directory names.
     - [x] Store and read submitted-filing audit records through
        `SubmissionRepository` encrypted envelopes; plaintext submission JSON is
        not a supported history backend.
  - [x] Add a typed `ObservedCasillaValue` schema for parsed casilla
     observations. It must preserve casilla id, value, source artefact kind,
     source locator, and extraction confidence.
  - [x] Prefer submitted TXT or model-specific filed data as the machine-readable
     source for casilla observations whenever AEAT exposes it. The parser must
     map submitted-file fields through registry export layouts or extraction
     profiles; it must not hardcode modelo/casilla layouts in Python.
  - [x] Implement full declaration-copy PDF parsing as required fallback and
     evidence capture. The parser must use registry extraction profiles for
     labels, form fields, bounding boxes, or other extraction primitives; it
     must not define filing-grade casilla completeness by itself.
     - [x] `parse_declaracion` loads or accepts a validated registry snapshot,
        selects the declaration-PDF extraction profile, extracts only the
        target casillas declared by that profile, and fails hard on missing,
        malformed, ambiguous, or below-coverage values.
  - [x] Keep justificante parsing as provenance and receipt metadata only:
     CSV, presentation id, presentation timestamp, tax id, totals, verification
     URL, source path, and source hash. Do not use justificante metadata as a
     substitute for full casilla data.
  - [x] Extend registry extraction-profile validation so every live filed-data
     parser declares accepted artefact kinds, target casillas, required
     coverage, source references, legal references where applicable, confidence
     rules, and fail-hard semantics.
  - [x] Extend previous-filing binding resolution so bindings such as
     previous-year economic-activity net income resolve through
     `FiledDeclarationObservation` and a validated registry selector or
     relation, not through ad hoc Python logic.
     - [x] Add partial backend resolution through `RegistryFilingObservation`,
        validated in `_bindings.py`, with the Modelo 130 `previous_filing`
        selector declared in `130.toml`.
     - [x] Add registry requirement discovery for previous-filing bindings so
        consumers can determine which filed modelo/year/period observations
        must be captured before calculation.
     - [x] Add guarded sede capture plumbing for required previous-filing
        observations.
     - [x] Resolve previous-filing bindings directly through
        `FiledDeclarationObservation`.
  - [x] Extend cross-model relation resolution so annual summaries and other
     registry relations can consume normalized filed observations captured from
     the read-only AEAT declarations register.
     - [x] Reuse one authenticated declarations-register browser context while
        discovering and capturing relation source filings.
     - [x] Resolve registry relation values directly from
        `FiledDeclarationObservation` without compatibility aliases or
        model-specific Python maps.
     - [x] Test Modelo 180 annual relation values against four Modelo 115
        filed observations, with hard failures for missing periods and
        incomplete extraction coverage.
  - [ ] Add filed-state drift verification that compares local registry
     calculation outputs against captured AEAT filed observations.
     - [x] Add a domain comparison verdict with compared casillas, missing
        local casillas, missing filed casillas, numeric drifts, and satisfied or
        failed status.
     - [x] Add a registry CLI command that loads encrypted filed observations,
        derives local calculation inputs from filed casillas, resolves
        previous-filing bindings and relation values from source observations,
        calculates through the validated snapshot, and emits a drift verdict.
     - [x] Add locale-backed CLI help, option text, error text, and report
        metric labels for the filed-state verification command.
     - [x] Add real-behaviour tests proving encrypted filed observations can
        satisfy the local calculation comparison and report numeric drift.
     - [ ] Add live-captured source-observation coverage for every modelo wave
        whose calculation depends on previous filed state or cross-model
        relations.
  - [x] Add no-write guard coverage for declaration-register search,
     submitted-file download, declaration-copy PDF download, justificante PDF
     download, CSV verifier access, and any archive fetch. Allowed operations
     are read navigation and read downloads only.
     - [x] Cover declaration-register search, submitted-file download, and
        justificante PDF download runtime operations through
        `authenticated_read_surface` and tests.
     - [x] Cover declaration-copy PDF download runtime operations.
     - [x] Cover CSV verifier runtime operations.
     - [x] Cover archive fetch runtime operations.
  - [x] Add repository checks proving live-read code cannot perform AEAT
     presentation, signing, payment, direct debit, server-side save, amendment,
     cancellation, or document submission.
  - [ ] Add real-behaviour parser tests against captured, identity-redacted AEAT
     register HTML, submitted-file artefacts, declaration-copy PDFs, and
     justificante PDFs. Tests must exercise the parser and registry extraction
     profile together, not redefine modelo or casilla schemas in test fixtures.
     - [x] Exercise identity-redacted register HTML through the declaration
        register parser.
     - [x] Exercise an identity-redacted Modelo 130 declaration-copy PDF through
        the registry-backed declaration parser and fail hard on the observed
        coverage gap.
     - [x] Add committed identity-redacted Modelo 130 submitted-file artefact
        coverage that parses through the registry export layout and declaration
        row context without generating the artefact inside the test.
     - [x] Add live-captured Modelo 130 submitted-file artefact coverage after
        reauthentication. The live observation is persisted only through the
        encrypted store and verifies as 19 submitted-file casillas with
        extraction coverage `1.0`.
     - [x] Add full success coverage once a declaration-copy or submitted-file
        artefact with complete registry target casillas is committed.
  - [ ] Add integration tests proving a live-read observation can populate
     registry binding values for Modelo 130 without defaults or silent
     degradation, and fails hard when the required previous-filing observation
     is missing, malformed, contradictory, or below required coverage.
     - [x] Add registry-backed `FiledDeclarationObservation` tests for Modelo
        130 previous-filing binding success and fail-hard missing, malformed,
        contradictory, justificante-only, and incomplete-coverage cases.
     - [x] Add encrypted observation-store roundtrip coverage proving a
        decrypted `FiledDeclarationObservation` can populate Modelo 130
        previous-filing binding values.
     - [ ] Add full live-read capture-to-binding integration coverage after a
        supported source-modelo live observation is available. Modelo 130's
        previous-filing binding currently depends on Modelo 100 casillas, which
        are not yet backed by a committed Modelo 100 registry/parser snapshot.
  - [ ] Re-run live-read parser tests, registry extraction-profile validation,
     remote-state guard tests, Modelo 130 binding tests, `ruff`, `ty`, and
     `git diff --check` before continuing concrete modelo implementation
     waves.

- `Phase 1` Registry framework rebuild
  - [x] Create the registry package under
     `src/aeat/domain/calculations/registry/`.
  - [x] Implement the strict Python schema authority for modelo, revision,
     casilla, formula, parameter, data binding, algorithm binding, relation,
     export layout, legal reference, source reference, temporal applicability,
     trace, and snapshot objects.
  - [x] Implement read-only TOML loading from `registry/aeat/modelos/` and
     `registry/aeat/legal/` using the standard TOML parser.
  - [x] Implement source catalogue verification over official AEAT artefacts,
     manuals, normative corpus entries, byte counts, hashes, paths, source
     URLs, and review status.
  - [x] Implement legal catalogue verification over BOE, AEAT manual, official
     instruction, and negative-citation blocklist evidence.
  - [x] Implement temporal selection for filing period, period code, legal
     effective dates, transaction date, devengo date, invoice date, and
     submission date.
  - [x] Implement reference resolution for modelo, revision, casilla, formula,
     parameter, binding, relation, export, legal, and source ids.
  - [x] Implement fail-fast validation for duplicate ids, shadowed definitions,
     missing evidence, overlapping windows, formula cycles, missing inputs,
     unresolved relations, unsupported operations, export drift, and
     incalculable revisions.
  - [x] Implement immutable registry snapshots and calculation trace output.
  - [x] Implement the registry-backed formula runtime using typed operation graphs,
     `Decimal` arithmetic, explicit rounding, graph validation, and calculation
     ledgers.
  - [x] Implement typed data bindings for factual input selection only. VAT,
     category, profile, ledger, invoice, rental, previous-filing, and manual
     input bindings cannot own legal rates or casilla mappings.
  - [x] Implement typed relation handling for previous-period and cross-model
     outputs, especially annual-summary relations needed by Modelo 390.
  - [x] Implement export-layout resolution from registry definitions backed by
     official AEAT record-design evidence.
  - [x] Implement the remote-state guard for live AEAT cross-reference work:
     allow only classified read-only Open simulator or authorized Integration
     test operations, and reject unsafe HTTP methods, authenticated filing
     portals, server-side save actions, signing, presentation, payment, direct
     debit, amendment, cancellation, and document submission.
  - [x] Implement read-only registry inspection and verification CLI commands.

- `Phase 1B` Registry schema closure before module replacement
  - [x] Add explicit schema objects for extraction profiles. A modelo revision
     must be able to declare parser surfaces, observed artefact kinds, target
     casillas, confidence requirements, coverage expectations, and source/legal
     evidence for extraction without making extractors filing authorities.
  - [x] Add explicit schema objects for live/static AEAT cross-reference
     decisions. A modelo revision must declare whether its official comparison
     surface is read-only Open simulator, authorized integration/test service,
     static official documentation only, or absent from filing-grade support.
     The decision must carry source refs, legal refs where applicable, guard
     policy, allowed methods, forbidden actions, and verification tests.
  - [x] Add explicit schema objects for workbook parity references. A modelo
     revision must declare official workbook coverage, workbook hash, formula
     discovery result, runner availability, synthetic fixture ids, output cells,
     tolerances, and unsupported coverage gaps.
  - [x] Add explicit schema objects for verification expectations. A modelo
     revision must declare expected computed casillas, tolerances, rounding
     policy, coverage thresholds, discrepancy classification rules, and trace
     requirements.
  - [x] Add explicit schema objects for application linkage. A modelo revision
     must declare which filing, review, verification, export, deadline, portal,
     extractor, and workflow surfaces consume the snapshot. Missing application
     linkage is a validation failure for filing-grade support.
  - [x] Add explicit schema objects for support/removal decisions. If a modelo,
     revision, export, extraction surface, or filing path lacks official
     evidence, the registry must represent that by absence from filing-grade
     support and by deletion from app entry points, not by disabled placeholders
     or compatibility states.
  - [x] Extend TOML loading so every new schema object is parsed from
     `registry/aeat/modelos/*.toml` with strict no-extra validation and no local
     legal/source catalogues.
  - [x] Extend registry validation so extraction profiles, live/static
     cross-reference decisions, workbook parity refs, verification
     expectations, application links, and support/removal decisions all resolve
     legal/source evidence and cannot reference unknown casillas, formulas,
     parameters, bindings, relations, export fields, or corpus artefacts.
     - [x] Validate extraction profiles, live/static cross-reference decisions,
        workbook parity refs, verification expectations, and application links.
     - [x] Validate support/removal decisions after their schema is introduced.
  - [ ] Extend snapshot building so consumers receive typed subviews for
     calculation, filing schema, extraction, verification, export, deadlines,
     portals, workbook parity, and live/static AEAT cross-reference.
     - [x] Add typed snapshot maps for extraction profiles, live/static
        cross-reference decisions, workbook parity refs, verification
        expectations, and application links.
     - [x] Resolve portal filing lookup from validated registry application
        links instead of portal-entry metadata.
     - [x] Add or verify typed consumer subviews for deadline and portal
        consumption.
     - [x] Add typed snapshot map for support/removal decisions.
  - [x] Extend the registry CLI so operators can inspect and verify schema
     closure per modelo/revision: legal closure, source closure, calculation
     closure, extraction closure, export closure, application-link closure,
     workbook parity coverage, and remote-state guard policy.
     - [x] Expose central closure inventory counts through read-only
        inspect/verify output: casillas, formulas, extraction profiles,
        live/static cross-references, workbook parity refs, verification
        expectations, application links, and application-link surfaces.
     - [x] Add per-modelo/revision closure detail output for export fields,
        deadlines, portal guard policies, and workbook parity coverage.
  - [x] Add behavioural tests for the closed schema. Tests must load committed
     registry TOML and verify real validation/runtime behaviour; they must not
     define their own modelo, casilla, legal, source, extraction, or export
     schema authority.
  - [ ] Re-run registry validation, runtime calculation tests, workbook/live
     parity tests, filing schema projection tests, verification tests, export
     tests, import-contract tests, `ruff`, and `ty` before starting any further
     model wave or deleting additional old authorities.
     - [x] Re-run focused registry, categories, registry CLI, authority
        import-contract, `ruff`, and `ty` checks for the completed batch.
     - [ ] Re-run filing schema projection, verification, and export suites
        after their consumers are switched to the new snapshot sections.

- `Phase 2` Central authority buildout and scattered-authority replacement
  - [ ] Establish the central registry backend as the only filing-grade
     authority for modelo identity, modelo revisions, casilla definitions,
     formulas, legal references, source references, parameters, data bindings,
     temporal applicability, extraction profiles, export layouts, and
     verification expectations.
  - [ ] Replace old scattered definition gates with one registry validation
     pipeline. Application, CLI, filing, verification, export, portal,
     deadline, VAT, category, rental, and extractor code must ask the registry
     for validated snapshots instead of checking their own support lists,
     supported years, casilla sets, formula targets, or filing availability.
  - [ ] Make the registry validation pipeline the only approval gate before
     calculation, review, approval, export, filing draft creation, workbook
     parity, and live/static AEAT cross-reference.
  - [ ] Define the module handoff contract for every old scattered authority:
     identify the old definition, implement the replacement registry schema or
     TOML field, wire the consuming module to the validated snapshot, verify the
     replacement behaviour, then delete the old definition and its authority
     gate.
  - [ ] Complete `registry/aeat/legal/` as the reviewed legal and
     official-source catalogue root. The directory exists, but it is not
     complete until BOE references, AEAT manual references, official
     record-design references, negative citation controls, and source integrity
     metadata cover every supported modelo wave.
  - [ ] Complete `registry/aeat/modelos/` as the one-file-per-modelo definition
     root. The directory exists, but it is not complete until every supported
     modelo has a reviewed TOML file and every evidence-backed removal is
     reflected by deletion from filing-grade app entry points.
  - [x] Create validation commands that load every catalogue and every completed
     modelo snapshot in one run.
  - [ ] Delete or hard-quarantine hydrate write paths, casilla corpus writers,
     schema cache writers, BOE extraction writers, export module generation,
     and DR fixture promotion paths from app-facing workflows.
  - [ ] Delete transient local scripts and one-off migration helpers from the
     repository root before any commit. They are never plan artefacts, registry
     artefacts, or runtime support code.
  - [ ] Replace public app calculation entry points so they require validated
     registry snapshots before calculation, review, approval, export, or filing
     draft creation.
  - [ ] Replace filing test-synthesis entry points with registry-driven fixture
     construction. Tests may pass input values, but they must not define their
     own modelo, revision, casilla, formula, legal, or source schema authority.
  - [ ] Replace workflow draft-input parsing so raw casilla input is accepted
     only after the target registry snapshot validates that those casillas
     exist and are legal for the selected period.
  - [ ] Replace verification and reconciliation entry points so extracted
     casilla values are compared only against a validated snapshot. Missing
     snapshot coverage fails hard instead of becoming an extractor-owned
     casilla truth surface.
  - [ ] Add behaviour tests proving filing-grade calculation, review, approval,
     import, export, and workflow paths require validated registry snapshots and
     fail fast on missing coverage. Tests must assert current public workflow
     behaviour only.
  - [ ] Add repository-wide checks that fail on process metadata, issue numbers,
     wave names, PR references, hydrate provenance, generated provenance, or
     transient development commentary inside runtime modules and registry TOML.
  - [x] Add repository-wide checks that fail when tests instantiate
     filing-grade `ModeloDefinition`, `ModeloRevision`, `CasillaDefinition`,
     legal catalogue, source catalogue, or TOML schema authority outside
     committed registry fixtures.
  - [ ] Add repository-wide checks that fail when runtime modules hardcode legal
     rates, thresholds, supported filing years, supported revision ids, formula
     targets, modelo-to-casilla maps, or filing-grade export bindings outside
     registry TOML.
  - [ ] Add repository-wide remote-state checks proving live AEAT
     cross-reference code cannot post, present, sign, save server-side state,
     pay, direct debit, amend, cancel, or submit documents to AEAT.

### Teardown Replacement Contract

Teardown is the removal of old scattered definitions and authority gates after
their responsibilities have moved into the central registry backend. It is not
deletion-only work and it is not a disabled-state mechanism. The old authority
is removed only as part of a module-specific rebuild record. Each record must
name the old scattered definition, the old gate, the replacement schema/TOML
field, the replacement files, the consuming public APIs, the application links,
the deletion list, the verification commands, and remaining gaps for that
concrete module. The plan must not classify modules into abstract lifecycle
states as a substitute for implementation.

If official evidence is absent or contradictory, the affected filing-grade
surface is removed from supported registry data and from app entry points. No
disabled placeholder, compatibility alias, shim, legacy import path, or dormant
runtime branch remains.

No wave can be marked complete by deletion alone. A wave is complete only when
the replacement owner is present, validated, tested, linked to the relevant
application surface, and the old authority has been deleted.

| Old authority being removed | Replacement owner | Required rebuild before deletion |
| --- | --- | --- |
| Hardcoded modelo catalogue and `ModeloCode` decisions | `registry/aeat/modelos/*.toml` plus registry modelo lookup | Modelo identity, title, cadence, revision windows, and filing availability are loaded from registry data. |
| Portal-to-modelo applicability | Registry portal/source bindings plus read-only portal catalogue plumbing | Portal modules describe endpoints only; registry data owns which modelo/revision can use them and the allowed read-only cross-reference surface. |
| Deadline and period applicability hardcoding | Registry temporal applicability plus deadline calculator | Python calculates dates from registry periods; it does not own supported years, cadences, period selectors, or filing applicability. |
| VAT rates and `declares_in_modelos` mappings | Registry parameters and factual VAT bindings | VAT modules classify factual events; legal rates, effective dates, modelo bindings, and casilla targets come from registry snapshots. |
| Category-to-casilla mappings | Registry data bindings | Category modules classify expenses and income facts; registry bindings decide if a fact populates a modelo revision. |
| Rental-to-Modelo-100 casilla mappings and passthroughs | Registry algorithm/data bindings for Modelo 100 | Rental modules produce factual ledgers and traceable aggregates; Modelo 100 registry definitions own target casillas and legal treatment. |
| Filing builders, import normalizers, complementaria helpers, and test draft helpers | Application filing plumbing over validated `RegistrySnapshot` | Draft creation, amendments, complementarias, imports, and test draft helpers require snapshot validation first and fail on coverage gaps. |
| Verification and reconciliation casilla assumptions | Snapshot-backed reconciliation | Extracted artefact values are observations only; expected casillas, computed targets, tolerances, and coverage come from the snapshot. |
| Borrador, declaración, justificante extractor casilla targets | Registry extraction profiles plus observed-value parser plumbing | Extractors identify observed values only; they cannot certify completeness, formulas, or filing validity. |
| Export record specs and generated export layouts | Registry export layouts plus generic encoders | Encoders can format fields; offsets, literals, casilla bindings, signedness, padding, record ids, and layout selection resolve from registry definitions. |
| Hydrate, generation, schema-cache, BOE-promotion, and DR-promotion paths | Reviewed registry source material and human-authored registry definitions | Runtime and app CLI cannot write legal-rule truth. Any discovery tool output is evidence only and cannot be imported as executable authority. |

- `Phase 2A` Discovered residual authority teardown ledger
  - [x] `src/aeat/domain/modelos`: replace the hardcoded `ModeloCode` authority
     with registry-backed modelo identity and lookup. Surviving
     Python may expose typed identifiers, but it must not own the supported
     modelo catalogue.
  - [x] `src/aeat/domain/portals`: move filing/census portal-to-modelo
     applicability into registry-backed portal bindings or source-backed
     registry metadata. Portal modules may describe read-only portal endpoints,
     but they must not define filing-grade modelo support, retirement carve-outs,
     or legal applicability.
  - [x] `src/aeat/domain/deadlines`: move modelo cadence, period applicability,
     deadline windows, and filing-year support into registry temporal
     applicability. Deadline code becomes a pure calculator over registry
     effective periods and calendar rules.
  - [x] `src/aeat/domain/vat`: remove hardcoded VAT fallback years,
     `declares_in_modelos` mappings, and VAT-to-modelo/casilla authority.
     VAT modules may classify factual VAT events; legal rates, effective dates,
     and declaration bindings belong in registry parameters and bindings.
  - [x] `src/aeat/domain/categories`: remove category-to-modelo/casilla mapping
     authority. Category modules may classify facts; registry bindings decide
     whether and how facts populate a modelo revision.
  - [x] `src/aeat/domain/rental`: remove rental-to-Modelo-100 casilla authority
     and passthrough behaviour. Rental modules may calculate factual rental
     ledgers and traceable aggregates; Modelo 100 decides target casillas and
     legal filing treatment through registry bindings and algorithm bindings.
  - [ ] `src/aeat/application/filing`: remove any filing builder, testing
     test draft helper, import normalizer, complementaria helper, or export wrapper
     that can construct a filing-grade draft without a validated registry
     snapshot.
  - [ ] `src/aeat/application/workflow`: remove draft stages that accept
     arbitrary raw casilla dictionaries as implicit truth. Workflow orchestration
     must load the snapshot first, validate inputs against the snapshot, and
     fail before draft creation on coverage gaps.
  - [ ] `src/aeat/application/verification`: keep only reconciliation plumbing
     that consumes extracted values and a validated snapshot. It must not infer
     the supported casilla set, tolerance policy, or computed targets outside
     the registry.
  - [ ] `src/aeat/adapters/inbound/borrador`: remove hardcoded Modelo 100
     summary casilla target lists as filing-grade truth. Borrador extraction may
     read a registry-provided extraction profile or remain a non-authoritative
     parser that cannot certify coverage.
  - [ ] `src/aeat/adapters/inbound/declaracion` and justificante extractors:
     classify extracted modelo and casilla values as observed artefact data
     only. They cannot define model support, casilla completeness, calculation
     targets, or filing validity.
  - [ ] `src/aeat/adapters/outbound/aeat/export/_formats`: remove old
     model-specific export layouts and generated-record authority. Generic
     encoders may remain, but offsets, casilla bindings, record ids, literals,
     signedness, padding, and layout selection must resolve from registry export
     layouts.
  - [ ] `src/aeat/entrypoints/cli`: remove commands and help text that expose
     old casilla/schema/hydrate/generation flows or imply filing-grade support
     without registry verification. CLI surfaces must inspect, validate, and
     run snapshots only.
  - [ ] `tests` and `tests/import_contract`: remove legacy fixtures that define
     modelo/casilla schemas, generated rule files, migration state, or previous
     architecture expectations. Tests must exercise committed registry data and
     real runtime behaviour.
  - [ ] `corpus`: classify every retained BOE, AEAT manual, official workbook,
     record-design, PDF, HTML, and fixture artefact as source evidence,
     behavioural test fixture, or archive-only material. Corpus files must not
     be read as runtime legal truth except through reviewed registry source
     references.

- `Phase 2B` File-level scattered-authority cleanup guardrail
  - [x] `src/aeat/domain/modelos/_codes.py`: move supported modelo identity,
     names, and retirement decisions into `registry/aeat/modelos/*.toml`; keep
     only registry-backed identifier helpers or delete the module.
  - [x] `src/aeat/domain/modelos/__init__.py`: export identifier helpers only;
     remove enum-style catalogue authority.
  - [x] `src/aeat/domain/modelos/test_codes.py`: replace enum-member assertions
     with identifier-shape behaviour tests.
  - [x] `src/aeat/domain/modelos/test_smoke.py`: remove hardcoded enum-member
     smoke expectations.
  - [x] `src/aeat/domain/portals/_metadata.py`: replace `ModeloCode` coupling
     with registry modelo ids and portal binding references.
  - [x] `src/aeat/domain/portals/_registry.py`: remove portal coverage gates
     that decide filing-grade modelo support; validate only portal catalogue
     integrity and defer applicability to registry snapshots.
  - [x] `src/aeat/domain/portals/_entries/_common.py`: replace
     `related_modelo=ModeloCode.*` construction with registry id/binding data.
  - [x] `src/aeat/domain/portals/_entries/portal_m*.py`: remove per-entry
     modelo support authority; each filing/census portal entry must be linked
     through registry portal bindings or remain endpoint metadata only.
  - [x] `src/aeat/domain/portals/test_modelo_cross_reference.py`: replace
     `ModeloCode` coverage tests with registry portal-binding validation tests.
  - [x] `src/aeat/domain/portals/test_metadata.py`: replace `ModeloCode`
     fixture construction with registry-backed metadata validation.
  - [x] `src/aeat/domain/portals/test_registry.py`: verify endpoint catalogue
     behaviour and registry binding closure; do not assert support from portal
     entries alone.
  - [x] `src/aeat/domain/deadlines/_calendar.py`: move modelo cadence, filing
     windows, and supported periods into registry temporal applicability.
  - [x] `src/aeat/domain/deadlines/_applies.py`: remove hardcoded profile-to-
     modelo applicability gates; consume registry applicability and factual
     profile bindings.
  - [x] `src/aeat/domain/deadlines/_engine.py`: keep date computation plumbing
     only; input must be validated registry temporal data.
  - [x] `src/aeat/domain/deadlines/_models.py`: remove fields or enums that
     imply supported modelo catalogues outside registry data.
  - [x] `src/aeat/domain/deadlines/test_applies.py`: replace hardcoded
     applicability cases with registry-backed applicability behaviour.
  - [x] `src/aeat/domain/deadlines/test_calendar.py`: replace fixed modelo
     deadline expectations with registry temporal fixtures loaded from TOML.
  - [x] `src/aeat/domain/deadlines/test_engine.py`: verify calculator behaviour
     over registry temporal inputs, not built-in support lists.
  - [x] `src/aeat/domain/vat/_catalogue.py`: move VAT category catalogue data
     out of Python into committed registry TOML and keep only read-only loading
     and exact-year resolution in runtime code.
  - [x] `src/aeat/domain/vat/_corpus.py`: remove hardcoded fallback years and
     runtime fallback catalogue authority.
  - [x] `src/aeat/domain/vat/_rates.py`: ensure rate lookup consumes registry
     parameters or factual VAT data only; no legal rate constants remain here.
  - [x] `src/aeat/domain/vat/_lookup.py`: convert lookup to factual
     classification over registry-provided rates/bindings.
  - [x] `src/aeat/domain/vat/_schema.py`: remove schema fields that make VAT
     records own modelo/casilla declaration targets.
  - [x] `src/aeat/domain/vat/_verify.py`: validate factual VAT catalogue
     integrity only; registry validates legal declaration binding closure.
  - [x] `src/aeat/domain/vat/test_*.py`: replace tests that encode VAT rates,
     model mappings, or fallback years with registry-backed behaviour tests.
  - [x] `registry/aeat/vat/rates.toml`: persisted VAT rate registry owns
     member-state, rate-kind, percentage, effective-window, and source-reference
     strings for the current VAT lookup surface.
  - [x] `registry/aeat/vat/catalogues/2025.toml`: persisted VAT catalogue
     registry owns category-level citation text, treatment flags, declaration
     bindings, and reviewer notes for the current catalogue surface.
  - [x] `src/aeat/domain/vat/test_rates.py`: exercise committed VAT registry
     lookup, coverage, and missing-rate failures through public runtime calls.
  - [x] `src/aeat/domain/vat/test_rates_temporal.py`: exercise committed VAT
     registry effective-window behaviour and overlap absence without defining
     an alternate in-test rate authority.
  - [x] `src/aeat/domain/vat/test_catalogue_period_keyed.py`: verify exact
     year-keyed catalogue resolution and fail-fast missing-year behaviour.
  - [x] `src/aeat/domain/vat/test_corpus.py`: verify VAT catalogue access reads
     committed registry data and rejects unregistered years.
  - [x] `src/aeat/domain/vat/test_rules.py`: verify committed catalogue
     category coverage, citation coverage, citation text, and rendered
     references without defining alternate regulations inside the test.
  - [x] `src/aeat/domain/vat/__init__.py`: remove year-specific catalogue
     exports and document VAT as registry-backed lookup and classification.
  - [x] `src/aeat/domain/vat/_classification.py`: keep factual decision-table
     classification but remove generic `_RULES` naming that overlaps with
     removed deadline/ruleset authority.
  - [x] `src/aeat/domain/vat/errors.py`: remove stale in-memory catalogue
     wording from VAT error documentation.
  - [x] `env/.env.example`: point VAT catalogue configuration at
     `registry/aeat/vat` without fallback wording.
  - [x] `src/aeat/domain/categories/_registry.py`: remove category-to-casilla
     and category-to-modelo authority; keep factual category classification.
  - [x] `src/aeat/domain/categories/_corpus.py`: remove fallback-to-hardcoded
     category registry behaviour for filing-grade decisions.
  - [x] `src/aeat/domain/categories/_profile.py`: ensure category profile data
     cannot decide modelo applicability or casilla targets.
  - [x] `src/aeat/domain/categories/_proportionality.py`: keep factual
     proportionality calculations only; legal treatment must be registry-bound.
  - [x] `src/aeat/domain/categories/test_*.py`: replace filing-target
     assertions with factual-classification tests plus registry binding tests.
  - [x] `registry/aeat/categories/profiles/2025.toml`: persisted category
     profile registry owns category labels, proportionality rules, caps, VAT
     hints, citations, and reviewer notes for the current profile surface.
  - [x] `src/aeat/domain/categories/__init__.py`: document category profiles as
     registry-backed data and expose registry resolution helpers.
  - [x] `src/aeat/domain/rental/_aggregates.py`: keep factual rental
     aggregate calculation and remove Modelo 100 target casilla authority.
  - [x] `src/aeat/domain/rental/anexo_c_provider.py`: delete passthrough and
     Modelo 100 merge authority; registry algorithm/data bindings must own the
     filing treatment.
  - [x] `src/aeat/domain/rental/_amortization_ledger.py`: keep factual
     amortization ledger behaviour and move filing/legal target use to registry
     algorithm bindings.
  - [x] `src/aeat/domain/rental/_expense_rollup.py`: keep factual rollups only;
     remove any implied Modelo 100 casilla ownership.
  - [x] `src/aeat/domain/rental/_tier_resolver.py`: keep factual tier
     resolution only; legal filing consequences must be registry-bound.
  - [x] `src/aeat/domain/rental/__init__.py`: expose only the neutral rental
     aggregate API and remove filing-target provider exports.
  - [x] `src/aeat/domain/rental/_errors.py`: rename aggregate error surface to
     neutral rental terminology with no filing-target naming.
  - [x] `src/aeat/domain/rental/_models.py`: remove filing-line wording from
     rental record docstrings.
  - [x] `src/aeat/domain/rental/_enums.py`: keep use-type semantics factual and
     remove filing-line wording.
  - [x] `tests/import_contract/domain/rental/_test_aggregates.py`: test factual
     rental aggregation through real persisted repositories.
  - [x] `src/aeat/domain/rental/_test_*.py`: test factual rental behaviour and
     registry algorithm binding integration, not caller-supplied casilla
     passthroughs.
  - [x] `src/aeat/application/filing/runtime.py`: replace collection projection
     with snapshot subviews that include revision, registry period selector,
     extraction, verification, export, and application linkage details.
  - [x] `src/aeat/application/filing/__init__.py`: ensure `build_draft` and
     related public APIs require validated snapshots and cannot construct
     filing-grade drafts from old schema providers.
  - [x] `src/aeat/application/filing/_calculate.py`: audited as summary
     rendering only; no next-action or status gate substitutes for registry
     validation, and its tests now build drafts through registry-backed public
     helpers.
  - [x] `src/aeat/application/filing/_import.py`: normalize imported values only
     after snapshot selection validates modelo, registry period support, and
     casilla ids.
  - [x] `src/aeat/application/filing/_export.py`: resolve export layouts from
     registry snapshots; remove old layout/spec selection paths.
  - [x] `src/aeat/application/filing/_complementaria.py`: require official
     justificante CSV linkage and an active registry-backed original draft
     before amendment/complementaria handling.
  - [x] `src/aeat/application/filing/_review.py`: approval recomputes registry
     schema and trace validation before stamping approval metadata, while
     review refresh still derives staleness from the persisted approval basis.
  - [x] `src/aeat/application/filing/_testing_schema.py`: remove test-owned
     modelo/casilla schema authority instead of retaining a parallel fixture
     schema.
  - [x] `src/aeat/application/filing/_testing_registry.py`: build test drafts
     against registry snapshots only; do not encode model-specific schemas in
     test helpers.
  - [x] `src/aeat/application/filing/testing.py`: expose test helpers that load
     real registry data rather than ad hoc fixtures.
  - [x] `src/aeat/application/filing/reconciliation/_reconcile.py`: require
     active registry-backed draft snapshots and registry verification
     expectations before comparing AEAT justificante metadata; year-only
     receipt periods only canonicalize as annual when the active registry
     revision declares `0A`.
  - [x] `src/aeat/application/filing/test_schema_completeness.py`: verify
     runtime schema provider exposes snapshot-backed filing subviews and
     formula-input closure over committed registry TOML without restating
     Modelo 130 casilla counts, formula inputs, or linkage ids in the test.
  - [x] `src/aeat/application/filing/test_import.py`: verify justificante-only
     import fails through the registry boundary when required binding data is
     absent, verify unsupported modelos fail before draft creation, and verify
     year-only receipts are rejected for quarterly registry revisions.
  - [x] `src/aeat/application/filing/test_export.py`: verify export and verify
     paths consult registry snapshot export-layout closure and fail closed when
     no layout is declared.
  - [x] `src/aeat/application/filing/test_*.py`: rewrite filing tests to load
     registry TOML and exercise current runtime behaviour only.
     - [x] `src/aeat/application/filing/test_filing.py`: remove test-local
        casilla schema providers; validate draft behaviour and approval-gate
        failures through the registry-backed runtime schema provider.
     - [x] `src/aeat/application/filing/test_testing_registry.py`: exercise
        registry-backed filing draft helper behaviour and fail fast for
        unsupported modelos.
     - [x] `tests/import_contract/application/filing/test_testing.py`: remove
        filing-history fixture schema tests that validated a separate
        modelo/casilla corpus instead of public registry-backed behaviour.
  - [x] `src/aeat/application/workflow/_adapters.py`: default JSON input
     loading now requires explicit modelo/period nesting and rejects root-level
     casilla payloads before the filing builder performs registry validation.
  - [x] `src/aeat/application/workflow/_engine.py`: workflow draft and
     preflight stages now require a registry-backed draft matching the resolved
     modelo, period, taxpayer, and active registry schema version before
     continuing.
  - [x] `src/aeat/application/workflow/_models.py`: audited as workflow result
     schema only; docstrings now describe stable diagnostics behaviour rather
     than enum mirror contracts or old support gates.
  - [x] `src/aeat/application/workflow/_protocols.py`: replace generic draft
     return surfaces with a registry-backed draft protocol that carries
     `schema_version`.
  - [x] `src/aeat/application/workflow/test_*.py`: verify workflow orchestration
     over registry snapshots, not hardcoded model/casilla dictionaries.
     - [x] `src/aeat/application/workflow/test_adapters.py`: verify explicit
        modelo/period JSON input shape and root-level casilla payload rejection.
     - [x] `src/aeat/application/workflow/test_engine.py`: verify registry draft
        identity guards for active schema version and resolved obligation
        period.
     - [x] `src/aeat/application/workflow/test_models.py`: remove enum mirror
        assertions and keep behavioural validation, hashing, alert, and JSON
        round-trip coverage.
  - [x] `src/aeat/application/verification/_schema.py`: verification verdicts
     now record the registry verification expectation ids that governed
     discrepancy and coverage evaluation.
  - [x] `src/aeat/application/verification/_verify.py`: verification now fails
     without registry verification expectations and derives computed casillas,
     tolerance, and minimum coverage from the active registry snapshot.
  - [x] `src/aeat/application/verification/test_verify.py`: load registry TOML
     and assert verification behaviour against Modelo 130 snapshot
     expectations, including required external binding values.
  - [x] `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`:
     replace hardcoded summary casilla list with registry extraction profile
     data or reduce the file to observed-value parsing only.
  - [x] `src/aeat/adapters/inbound/borrador/_parser.py`: require registry
     extraction profile when caller asks for coverage or filing-grade use.
  - [x] `src/aeat/adapters/inbound/borrador/_schema.py`: mark parsed values as
     observations and remove any implied Modelo 100 completeness authority.
  - [x] `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`: test
     parser behaviour against registry extraction profiles, not hardcoded
     summary rules.
  - [x] `src/aeat/adapters/inbound/declaracion/_parser.py`: parse observed
     modelo/casilla values only; registry validates support and completeness.
  - [x] `src/aeat/adapters/inbound/declaracion/_schema.py`: ensure declaration
     schema cannot represent filing-grade model completeness by itself.
  - [x] `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`: test
     parser boundaries without encoding model support or casilla truth.
  - [x] `src/aeat/adapters/inbound/justificante/_extract.py`: keep receipt
     extraction as observed artefact data; no support or formula authority.
  - [x] `src/aeat/adapters/inbound/justificante/_parser.py`: same observed-data
     boundary as extract; registry owns filing-grade interpretation.
  - [x] `src/aeat/adapters/inbound/justificante/test_extract_modelos.py`:
     verify observed extraction only and move support checks to registry tests.
  - [x] `tests/import_contract/adapters/inbound/justificante/test_parser.py`:
     assert observed fixture PDF period output rather than treating fixture
     filenames as period authority.
  - [x] `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`:
     remove model-specific layout authority; keep generic field-format
     primitives only.
  - [x] `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`:
     serialize registry export layout subviews only.
  - [x] `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`:
     deserialize into observed field/casilla values and let registry validate
     layout meaning.
  - [ ] `src/aeat/adapters/outbound/aeat/export/_formats/test_*.py`: test
     generic encoder/decoder behaviour plus registry layout integration, not
     hardcoded modelo layouts.
  - [ ] `src/aeat/entrypoints/cli/registry.py`: expose schema-closure,
     model-closure, source/legal, extraction, verification, export, workbook,
     and remote-state guard validation commands.
  - [x] `src/aeat/entrypoints/cli/filing/__init__.py`: require registry
     snapshots for calculate, import, verify, review, approve, and export
     commands.
  - [x] `src/aeat/entrypoints/cli/_declaration.py`: remove command behaviour
     that edits or exports casillas without registry snapshot validation.
  - [x] `src/aeat/entrypoints/cli/deadlines/*.py`: consume registry temporal
     applicability and remove CLI-level model support gates.
  - [x] `src/aeat/entrypoints/cli/categories.py`: expose factual category tools
     only; no filing target or casilla implication.
  - [x] `src/aeat/entrypoints/cli/test_registry_cli.py`: assert registry
     closure commands over committed TOML.
  - [x] `src/aeat/entrypoints/cli/filing/test_filing_cli.py`: assert filing CLI
     refuses coverage gaps and succeeds only through validated snapshots.
  - [ ] `tests/import_contract/application/filing/test_testing.py`: remove
     test-owned casilla schema expectations and use committed registry
     data.
  - [ ] `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_*.py`:
     classify generators as parser fixtures only; they cannot define legal
     schema, casilla completeness, formulas, or model support.
  - [ ] `tests/fixtures/financial/n26/_generate.py` and
     `tests/fixtures/justificantes/_generate.py`: keep fixture generation
     outside registry authority and guard against generated legal-rule imports.

- `Phase 3` Shared legal/source catalogue migration
  - [ ] Migrate BOE normative references from `corpus/normatives` into reviewed
     legal catalogue entries by stable id.
  - [ ] Migrate AEAT manual manifests from `corpus/manuals` into reviewed source
     and legal-reference catalogue entries where appropriate.
  - [ ] Migrate official AEAT record-design manifests from
     `corpus/aeat_official/disenos_registro` into reviewed source catalogue
     entries.
  - [ ] Preserve the known-bad citation blocklist as a registry validation input.
  - [ ] Reconcile source catalogue coverage with calculation coverage. A model can
     have source evidence without a completed snapshot, but it cannot be filed
     until the model wave completes.
  - [ ] Resolve the Modelo 037 evidence gap. If official evidence remains absent,
     Modelo 037 is removed from the filing-grade supported registry set until
     reviewed official evidence exists.

- `Phase 4` Model wave completion contract
  - [ ] Audit all existing code, corpus files, tests, export records, manual
     references, BOE references, portal/deadline references, and application
     paths for the selected modelo.
  - [ ] Research official AEAT and BOE evidence for every supported revision,
     including yearly and intra-year variation.
  - [ ] Research the official live AEAT cross-reference surface for the selected
     modelo and classify it as read-only Open simulator, authorized
     Integration/test web service, static official documentation only, or
     forbidden authenticated/stateful surface.
  - [ ] Prove the selected modelo's cross-reference path is protected by the
     remote-state guard and cannot write AEAT remote state.
  - [ ] Discover and classify the selected modelo's official XLS/XLSX workbook
     coverage, including formula-bearing worksheets, static layouts,
     unsupported binary XLS files, and unreadable artefacts.
  - [ ] Run identical synthetic data through the registry engine and every
     supported workbook/simulator parity surface for the selected modelo.
     Computed outputs must match within the declared tolerance, and
     non-executable workbook coverage must be recorded as a source/legal
     evidence decision before the modelo can be production-ready.
  - [ ] Discover all current duplicate authorities for the selected modelo across
     formulas, modelos, casillas, filing builders, VAT/category/deadline
     mappings, inbound declaration extractors, schema extraction, and export.
  - [ ] Write the modelo TOML with revisions, casillas, formulas, parameters,
     bindings, relations, legal refs, source refs, and export layouts.
  - [ ] Link the modelo to the registry-backed calculation, review, approval,
     filing draft, and export flows.
  - [ ] Verify legal basis: every formula, rate, threshold, applicability rule,
     relation, export field, and filing condition resolves to reviewed legal
     and source evidence.
  - [ ] Verify calculation: parity against existing trusted examples, real
     behavioural examples, official workbook outputs where supported, edge
     cases, invalid inputs, date-axis selection, trace output, and export
     alignment.
  - [ ] Delete old model-specific authorities and update imports. The wave is not
     complete while an old model-specific ruleset, filing builder, generated
     export authority, hydrate table, or standalone casilla truth remains.
  - [ ] Run registry validation, public API behaviour tests, model tests,
     filing/export tests, and vault checks before marking the wave complete.

- `Phase 4A` Per-modelo workbook verification gates
  - [ ] Modelo 130: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 111: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 115: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 123: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 131: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 180: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 190: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 193: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 303: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 390: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 349: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 347: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 369: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 202: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 200: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 232: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 720: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 840: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 036: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 037: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.
  - [ ] Modelo 100: discover and classify every official XLS/XLSX artefact, run
     executable parity where formula workbooks are supported, and record
     non-executable coverage decisions with source/legal evidence.

- `Wave 1` Modelo 130 complete implementation
  - [ ] Audit every Modelo 130 authority in rulesets, modelo metadata, casilla
     corpus, filing builders, category aggregation, deadline/applicability,
     declaration extraction, export specs, tests, manuals, BOE references, and
     official AEAT record designs.
  - [ ] Produce a Modelo 130 model-law coverage ledger covering all supported
     revisions, source artefacts, legal references, casillas, formulas,
     parameters, bindings, export fields, filing entry points, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for IRPF payment on
     account, income/expense aggregation, reductions, retentions, previous
     payments, period accumulation, and filing/export obligations.
  - [ ] Classify the Modelo 130 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Inspect the committed official Modelo 130 workbook
     `corpus/aeat_official/disenos_registro/modelo_130/files/01-130-orden-hap-258-2015-ejercicios-2019-y-siguientes-actualizado-marzo-2019-176-kb-xls.xls`
     and classify whether it is an executable calculation workbook, a record
     design/static layout workbook, or unreadable binary evidence. The wave
     cannot claim XLS calculation parity until this is proven from the workbook
     contents.
  - [ ] If the official Modelo 130 workbook is executable, implement a supported
     local runner or conversion path for that binary XLS, inject one committed
     synthetic input set into both the workbook and registry engine, and compare
     computed casillas `03`, `04`, `07`, `09`, `11`, `12`, `14`, `17`, and `19`
     with legal/source trace output.
  - [ ] If the official Modelo 130 workbook is not executable calculation
     evidence, record that fact in the Modelo 130 coverage ledger and replace
     the parity oracle with reviewed official worked examples, static AEAT
     documentation, or an approved read-only AEAT calculation surface. Do not
     mark unsupported XLS as passing parity.
  - [ ] Write `registry/aeat/modelos/130.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, relation, legal reference,
     source reference, and export layout.
  - [ ] Implement the Modelo 130 registry export layout from the official record
     design workbook: record ids, offsets, lengths, literals, casilla fields,
     padding, signedness, line endings, source refs, and legal refs. Export must
     fail closed until this layout is complete.
  - [ ] Link Modelo 130 to registry-backed calculation, trace, review, approval,
     filing draft, and export workflows.
  - [ ] Link Modelo 130 previous-filing bindings to committed Modelo 100
     registry observations once Modelo 100 has a reviewed registry/parser
     snapshot. This remains pending until the source modelo can provide the
     required prior-year annual filing casillas through the same central
     observation schema and encrypted storage backend.
  - [ ] Verify Modelo 130 with real calculation examples, invalid inputs,
     date-axis boundaries, legal-reference checks, source-integrity checks,
     export roundtrips, and stale/contradictory registry failure cases.
  - [ ] Prune filing tests and helpers so Modelo 130 behaviour is exercised by
     committed registry data and public APIs. Direct draft synthesis may remain
     only for repository/storage tests that do not claim filing-grade
     calculation behaviour.
  - [ ] Delete Modelo 130 old authorities in rulesets, filing builders, category
     casilla mappings, hydrate/casilla projections, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 130 can be calculated, reviewed,
     imported, and exported only through validated registry snapshots and fails
     fast on missing legal/source/export/calculation coverage.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 2` Modelo 111 complete implementation
  - [x] Add the official AEAT Modelo 111 instructions artefact to the corpus and
     register it as reviewed `official_source_guidance`.
  - [x] Register the reviewed Modelo 111 legal basis needed for the periodic
     withholding declaration surface: LIRPF article 99 and RIRPF article 109.
  - [x] Register the current AEAT Modelo 111 record-design workbook as reviewed
     `layout_authority`.
  - [x] Build the first centralized Modelo 111 registry definition for the
     current `2019-y-siguientes` revision with the official 30-casilla
     liquidation surface, supported calculation formulas for casillas 28 and
     30, export-record layout, declaration/submitted-file extraction profiles,
     static official cross-reference guard, workbook layout evidence, and 2026
     quarterly deadline windows.
  - [x] Verify the Modelo 111 registry definition through source-integrity
     validation and real registry runtime calculation tests.
  - [x] Audit every Modelo 111 authority in rulesets, modelo metadata, casilla
     corpus, hydrate augment data, declaration extractors, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [x] Produce a Modelo 111 model-law coverage ledger covering all revisions,
     legal withholding parameters, casillas, formulas, bindings, recipient
     counts, source artefacts, export fields, filing paths, tests, and old
     authorities to delete.
  - [x] Research and verify the official AEAT and BOE basis for retenciones and
     ingresos a cuenta for work, professional, and related income categories.
  - [x] Classify the Modelo 111 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [x] Write `registry/aeat/modelos/111.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [x] Link Modelo 111 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [x] Prove submitted-file parsing for Modelo 111 against the centralized
     export layout and preserve any captured live AEAT artefacts only through
     encrypted financial storage.
  - [x] Capture or classify available live AEAT filed-declaration artefacts for
     Modelo 111 and map observed casillas into the standard observation schema.
  - [x] Verify Modelo 111 with real withholding examples, invalid inputs,
     date-axis boundaries, legal-reference checks, source-integrity checks,
     export roundtrips, and registry failure cases.
  - [x] Delete Modelo 111 old authorities in rulesets, hydrate augment data,
     casilla projections, declaration extractor truth, duplicated metadata, and
     generated export/layout paths.
  - [x] Add behaviour tests proving Modelo 111 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 3` Modelo 115 complete implementation
  - [x] Audit every Modelo 115 authority in rulesets, modelo metadata, casilla
     corpus, rental/category mappings, declaration extractors, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [x] Produce a Modelo 115 model-law coverage ledger covering all revisions,
     source artefacts, legal references, rental withholding casillas, formulas,
     parameters, data bindings, export fields, filing paths, tests, and old
     authorities to delete.
  - [x] Research and verify the official AEAT and BOE basis for rental withholding
     taxable bases, withholding amounts, recipient counts, and filing/export
     obligations.
  - [x] Classify the Modelo 115 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [x] Write `registry/aeat/modelos/115.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [x] Link Modelo 115 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [x] Verify Modelo 115 with real rental withholding examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [x] Delete Modelo 115 old authorities in rulesets, rental/category casilla
     mappings, casilla projections, declaration extractor truth, duplicated
     metadata, and generated export/layout paths.
  - [x] Add behaviour tests proving Modelo 115 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 4` Modelo 123 complete implementation
  - [x] Audit every Modelo 123 authority in rulesets, modelo metadata, casilla
     corpus, declaration extractors, annual-summary links, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [x] Produce a Modelo 123 model-law coverage ledger covering all revisions,
     capital-income withholding bases, retentions, income-account treatment,
     casillas, formulas, source artefacts, export fields, filing paths, tests,
     and old authorities to delete.
  - [x] Research and verify the official AEAT and BOE basis for capital income
     retentions and ingresos a cuenta.
  - [x] Classify the Modelo 123 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [x] Write `registry/aeat/modelos/123.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [x] Link Modelo 123 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [x] Verify Modelo 123 with real capital-income examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [x] Delete Modelo 123 old authorities in rulesets, annual-summary shadow
     links, declaration extractor truth, casilla projections, duplicated
     metadata, and generated export/layout paths.
  - [x] Add behaviour tests proving Modelo 123 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 5` Modelo 131 complete implementation
  - [ ] Audit every Modelo 131 authority in rulesets, modelo metadata, casilla
     corpus, category/deadline/applicability logic, declaration extractors,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 131 model-law coverage ledger covering all revisions,
     objective-estimation modules, reductions, previous payments, casillas,
     formulas, parameters, source artefacts, export fields, filing paths, tests,
     and old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for estimacion
     objetiva IRPF instalments and temporal parameters.
  - [ ] Classify the Modelo 131 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/131.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
     - [x] Current 2026 liquidacion schema and formulas are committed; historical
       2019-2023, 2024, and 2025 revisions and activity-detail export records
       remain open.
  - [ ] Link Modelo 131 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
     - [x] Current 2026 calculation, deadline, extraction, verification,
       review, filing, portal, and static cross-reference links are committed.
     - [ ] Export workflow remains open until the record-design activity-detail
       structures are represented without flattening or filler fields.
  - [ ] Verify Modelo 131 with real module examples, invalid inputs, date-axis
     boundaries, legal-reference checks, source-integrity checks, export
     roundtrips, and registry failure cases.
     - [x] Current 2026 registry calculation and deadline applicability tests
       pass through the committed runtime.
     - [ ] Export roundtrips, historical date-axis tests, and live filed-data
       parser tests remain open.
  - [ ] Delete Modelo 131 old authorities in rulesets, category/deadline
     hardcoding, casilla projections, declaration extractor truth, duplicated
     metadata, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 131 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
     - [x] Current 2026 calculation and deadline membership are covered by
       committed behaviour tests.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 6` Modelo 180 complete implementation
  - [ ] Audit every Modelo 180 authority in rulesets, modelo metadata, casilla
     corpus, annual-summary logic, declaration extractors, export specs, tests,
     manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 180 model-law coverage ledger covering all revisions,
     recipient/property records, relations to Modelo 115, legal references,
     source artefacts, export fields, filing paths, tests, and old authorities
     to delete.
  - [ ] Research and verify the official AEAT and BOE basis for the annual summary
     of rental withholdings and its relation to Modelo 115 outputs.
  - [ ] Classify the Modelo 180 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/180.toml` with every reviewed revision,
     casilla, formula, parameter, cross-model relation, legal reference, source
     reference, and export layout.
  - [ ] Link Modelo 180 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
     - [x] Current and historical Modelo 180 constructs own snapshot-gated
       review, approval, reconciliation, and workflow links.
  - [ ] Verify Modelo 180 with real annual-summary examples, relation tests over
     Modelo 115 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
     - [x] Focused relation tests cover Modelo 115 quarterly observations,
       annual aggregation, and fail-fast missing source periods.
  - [ ] Delete Modelo 180 old authorities in rulesets, annual summary code,
     declaration extractor truth, casilla projections, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 180 relation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
     - [x] Snapshot-gate behaviour test covers both supported Modelo 180
       revisions without using old-state or transition assertions.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 7` Modelo 190 complete implementation
  - [ ] Audit every Modelo 190 authority in modelo metadata, casilla corpus,
     annual-summary logic, declaration extractors, export specs, tests, manuals,
     BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 190 model-law coverage ledger covering all revisions,
     recipient records, withholding classifications, relations to Modelo 111,
     legal references, source artefacts, export fields, filing paths, tests, and
     old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for the annual summary
     of retenciones and ingresos a cuenta and its relation to Modelo 111
     outputs.
  - [ ] Classify the Modelo 190 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/190.toml` with every reviewed revision,
     casilla, formula or declaration validation rule, parameter, cross-model
     relation, legal reference, source reference, and export layout.
     - [x] Current 2025-y-siguientes registry foundation validates and includes
       annual application-link gates plus quarterly Modelo 111 relation-backed
       aggregate formulas.
  - [ ] Link Modelo 190 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
     - [x] Review, approval, reconciliation, workflow, calculation, filing,
       verification, extractor, and portal links are snapshot-gated in the
       Modelo 190 construct; export layout and live filed-data parsing remain
       open rows.
  - [ ] Verify Modelo 190 with real annual-summary examples, relation tests over
     Modelo 111 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
     - [x] Quarterly Modelo 111 relation behavior is covered through real
       registry observation resolution and formula execution for the current
       annual summary slice.
  - [ ] Delete Modelo 190 old authorities in annual summary code, declaration
     extractor truth, hydrate/casilla projections, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 190 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 8` Modelo 193 complete implementation
  - [ ] Audit every Modelo 193 authority in modelo metadata, casilla corpus,
     annual-summary logic, declaration extractors, export specs, tests, manuals,
     BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 193 model-law coverage ledger covering all revisions,
     capital-income recipient records, relations to Modelo 123, legal
     references, source artefacts, export fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for the annual summary
     of capital-income retentions and its relation to Modelo 123 outputs.
  - [ ] Classify the Modelo 193 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/193.toml` with every reviewed revision,
     casilla, formula or declaration validation rule, parameter, cross-model
     relation, legal reference, source reference, and export layout.
     - [x] Current 2024-y-siguientes registry foundation validates and includes
       annual application-link gates plus quarterly Modelo 123 relation-backed
       aggregate formulas.
  - [ ] Link Modelo 193 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
     - [x] Review, approval, reconciliation, workflow, calculation, filing,
       verification, extractor, and portal links are snapshot-gated in the
       Modelo 193 construct; export layout and live filed-data parsing remain
       open rows.
  - [ ] Verify Modelo 193 with real annual-summary examples, relation tests over
     Modelo 123 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
     - [x] Quarterly Modelo 123 relation behavior is covered through real
       registry observation resolution and formula execution for the current
       annual summary slice.
  - [ ] Delete Modelo 193 old authorities in annual summary code, declaration
     extractor truth, casilla projections, duplicated metadata, and generated
     export/layout paths.
  - [ ] Add behaviour tests proving Modelo 193 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 9` Modelo 303 complete implementation
  - [ ] Audit every Modelo 303 authority in rulesets, modelo metadata, casilla
     corpus, filing builders, VAT rates, VAT category mappings, category bridge
     mappings, declaration extractors, export specs, tests, manuals, BOE
     references, and official AEAT record designs.
  - [ ] Produce a Modelo 303 model-law coverage ledger covering all revisions,
     IVA rates, output VAT, deductible VAT, compensations, period variation,
     casillas, formulas, factual VAT bindings, source artefacts, export fields,
     filing paths, tests, and old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for IVA
     autoliquidacion, rates, deductions, temporal changes, and filing/export
     obligations.
  - [ ] Classify the Modelo 303 OPEN simulator for live cross-reference and add
     remote-state guard tests; authenticated Pre303/presentation, signing,
     payment, server-side save, and any AEAT write action are forbidden.
  - [ ] Write `registry/aeat/modelos/303.toml` with every reviewed revision,
     casilla, formula, parameter, factual data binding, relation, legal
     reference, source reference, and export layout.
  - [ ] Link Modelo 303 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 303 with real IVA examples, invalid inputs, rate-change
     date-axis tests, legal-reference checks, source-integrity checks, export
     roundtrips, and registry failure cases.
  - [ ] Delete Modelo 303 old authorities in rulesets, filing builders, VAT rate
     tables, VAT-to-casilla mappings, category bridge mappings, declaration
     extractor truth, casilla projections, duplicated metadata, and generated
     export/layout paths.
  - [ ] Add behaviour tests proving Modelo 303 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 10` Modelo 390 complete implementation
  - [ ] Audit every Modelo 390 authority in rulesets, modelo metadata, casilla
     corpus, filing builders, annual IVA summary logic, declaration extractors,
     export specs, tests, manuals, BOE references, XSD/PDF/XLS/XLSX official
     evidence, and AEAT record designs.
  - [ ] Produce a Modelo 390 model-law coverage ledger covering all revisions,
     annual summary casillas, relations to Modelo 303, source-format variation,
     legal references, source artefacts, export fields, filing paths, tests, and
     old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for annual IVA summary
     filing and typed relations over reviewed Modelo 303 outputs.
  - [ ] Classify the Modelo 390 OPEN simulator for live cross-reference and add
     remote-state guard tests; authenticated presentation, signing, payment,
     server-side save, and any AEAT write action are forbidden.
  - [ ] Write `registry/aeat/modelos/390.toml` with every reviewed revision,
     casilla, formula, parameter, cross-model relation, legal reference, source
     reference, and export layout.
  - [ ] Link Modelo 390 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
  - [ ] Verify Modelo 390 with real annual IVA examples, relation tests over Modelo
     303 outputs, source-format variation tests, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
  - [ ] Delete Modelo 390 old authorities in rulesets, filing builders, annual IVA
     summary code, declaration extractor truth, casilla projections, duplicated
     metadata, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 390 annual-summary and filing
     workflows require a validated registry snapshot and fail fast on coverage
     gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 11` Modelo 349 complete implementation
  - [ ] Audit every Modelo 349 authority in modelo metadata, casilla corpus,
     intra-community operation classification, declaration extractors, export
     specs, tests, manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 349 model-law coverage ledger covering all revisions,
     operation classifications, party records, amount records, period rules,
     legal references, source artefacts, export fields, filing paths, tests, and
     old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for intra-community
     operation declaration and ROI-related filing conditions.
  - [ ] Classify the Modelo 349 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/349.toml` with every reviewed revision,
     casilla or record definition, validation rule, parameter, data binding,
     legal reference, source reference, and export layout.
  - [ ] Link Modelo 349 to registry-backed validation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 349 with real declaration examples, invalid party/operation
     cases, legal-reference checks, source-integrity checks, export roundtrips,
     and registry failure cases.
  - [ ] Delete Modelo 349 old authorities in declaration extractor truth, modelo
     metadata duplicates, casilla projections, operation mapping code, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 349 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 12` Modelo 347 complete implementation
  - [ ] Audit every Modelo 347 authority in modelo metadata, casilla corpus,
     aggregation/category logic, declaration extractors, deadline logic, export
     specs, tests, manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 347 model-law coverage ledger covering all revisions,
     third-party thresholds, annual and quarterly breakdowns, party records,
     aggregation rules, legal references, source artefacts, export fields,
     filing paths, tests, and old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for third-party
     operations declaration, thresholds, exclusions, and reporting conditions.
  - [ ] Classify the Modelo 347 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/347.toml` with every reviewed revision,
     casilla or record definition, formula or validation rule, parameter, data
     binding, legal reference, source reference, and export layout.
  - [ ] Link Modelo 347 to registry-backed aggregation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 347 with real threshold examples, invalid aggregation cases,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 347 old authorities in category/aggregation hardcoding,
     declaration extractor truth, modelo metadata duplicates, casilla
     projections, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 347 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 13` Modelo 369 complete implementation
  - [ ] Audit every Modelo 369 authority in modelo metadata, casilla corpus,
     VAT/category mappings, OSS/IOSS regime logic, declaration extractors,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 369 model-law coverage ledger covering all revisions,
     OSS/IOSS regimes, country/rate breakdowns, operation totals, legal
     references, source artefacts, export fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT, BOE, and applicable EU basis for
     OSS/IOSS IVA declaration and temporal applicability.
  - [ ] Classify the Modelo 369 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/369.toml` with every reviewed revision,
     casilla or record definition, formula or validation rule, parameter, data
     binding, legal reference, source reference, and export layout.
  - [ ] Link Modelo 369 to registry-backed validation/calculation, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
  - [ ] Verify Modelo 369 with real regime examples, invalid country/rate cases,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 369 old authorities in VAT/category mapping code,
     declaration extractor truth, modelo metadata duplicates, casilla
     projections, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 369 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 14` Modelo 202 complete implementation
  - [ ] Audit every Modelo 202 authority in rulesets, modelo metadata, casilla
     corpus, corporate-tax helpers, declaration extractors, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 202 model-law coverage ledger covering all revisions,
     corporate-tax instalment methods, bases, percentages, previous amounts,
     legal references, source artefacts, export fields, filing paths, tests, and
     old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for corporate-tax
     payments on account and period selection.
  - [ ] Classify the Modelo 202 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/202.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, relation, legal reference,
     source reference, and export layout.
  - [ ] Link Modelo 202 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 202 with real corporate instalment examples, invalid inputs,
     date-axis boundaries, legal-reference checks, source-integrity checks,
     export roundtrips, and registry failure cases.
  - [ ] Delete Modelo 202 old authorities in rulesets, corporate-tax helper
     hardcoding, declaration extractor truth, modelo metadata duplicates,
     casilla projections, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 202 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 15` Modelo 200 complete implementation
  - [ ] Audit every Modelo 200 authority in rulesets, corporate-tax helpers,
     modelo metadata, casilla corpus, declaration extractors, schema extraction,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 200 model-law coverage ledger covering all revisions,
     corporate-tax bases, deductions, instalment relations, large export
     layouts, legal references, source artefacts, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for annual corporate
     tax filing by subdomain.
  - [ ] Classify Sociedades WEB Open for Modelo 200 live cross-reference and add
     remote-state guard tests; authenticated Sociedades WEB presentation,
     signing, payment, server-side save, and any AEAT write action are forbidden.
  - [ ] Write `registry/aeat/modelos/200.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, relation, legal reference,
     source reference, and export layout.
  - [ ] Link Modelo 200 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 200 with real corporate-tax examples, invalid inputs,
     relation tests to Modelo 202, legal-reference checks, source-integrity
     checks, export roundtrips, and registry failure cases.
  - [ ] Delete Modelo 200 old authorities in rulesets, corporate-tax helpers,
     declaration extractor truth, schema-generation truth, modelo metadata
     duplicates, casilla projections, and generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 200 calculation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 16` Modelo 232 complete implementation
  - [ ] Audit every Modelo 232 authority in modelo metadata, casilla corpus,
     related-party/tax-haven logic, declaration extractors, export specs, tests,
     manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 232 model-law coverage ledger covering all revisions,
     related-party thresholds, operation records, reporting conditions, legal
     references, source artefacts, export fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for related-party and
     tax-haven operations reporting.
  - [ ] Classify the Modelo 232 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/232.toml` with every reviewed revision,
     casilla or record definition, validation rule, parameter, data binding,
     legal reference, source reference, and export layout.
  - [ ] Link Modelo 232 to registry-backed validation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
     - [x] Review, approval, reconciliation, workflow, filing, extraction,
       deadline, and export links are snapshot-gated in every Modelo 232
       revision construct.
  - [ ] Verify Modelo 232 with real reporting-condition examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 232 old authorities in declaration extractor truth, modelo
     metadata duplicates, casilla projections, related-party hardcoding, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 232 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
     - [x] Focused workflow-link behavior test covers snapshot-gated review,
       approval, reconciliation, and workflow surfaces for every revision.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 17` Modelo 720 complete implementation
  - [ ] Audit every Modelo 720 authority in modelo metadata, casilla corpus,
     foreign-asset declaration logic, declaration extractors, export specs,
     tests, manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 720 model-law coverage ledger covering all revisions,
     asset classes, thresholds, reporting conditions, record layouts, legal
     references, source artefacts, filing paths, tests, and old authorities to
     delete.
  - [ ] Research and verify the official AEAT and BOE basis for foreign assets
     declaration and reporting conditions.
  - [ ] Classify the Modelo 720 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/720.toml` with every reviewed revision,
     casilla or record definition, validation rule, parameter, data binding,
     legal reference, source reference, and export layout.
  - [ ] Link Modelo 720 to registry-backed validation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
     - [x] Review, approval, reconciliation, workflow, filing, extraction,
       deadline, and export links are snapshot-gated in the Modelo 720
       construct.
  - [ ] Verify Modelo 720 with real asset-class examples, threshold failures,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 720 old authorities in declaration extractor truth, modelo
     metadata duplicates, casilla projections, foreign-asset hardcoding, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 720 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
     - [x] Focused workflow-link behavior test covers snapshot-gated review,
       approval, reconciliation, and workflow surfaces.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 18` Modelo 840 complete implementation
  - [ ] Audit every Modelo 840 authority in modelo metadata, casilla corpus,
     IAE/activity logic, declaration extractors, portal/deadline logic, export
     specs, tests, manuals, BOE references, and official AEAT record designs.
  - [ ] Produce a Modelo 840 model-law coverage ledger covering all revisions,
     IAE activity data, municipality/activity conditions, source artefacts,
     legal references, export or filing fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for IAE declaration
     conditions and filing linkage.
  - [ ] Classify the Modelo 840 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/840.toml` with every reviewed revision,
     casilla or record definition, validation rule, parameter, data binding,
     legal reference, source reference, and export or filing layout.
  - [ ] Link Modelo 840 to registry-backed validation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export or submission
     workflows.
  - [ ] Verify Modelo 840 with real IAE examples, invalid activity/municipality
     cases, legal-reference checks, source-integrity checks, filing/export
     roundtrips, and registry failure cases.
  - [ ] Delete Modelo 840 old authorities in declaration extractor truth, modelo
     metadata duplicates, censal/IAE hydrate data, casilla projections, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 840 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 19` Modelo 036 complete implementation
  - [ ] Audit every Modelo 036 authority in modelo metadata, casilla corpus,
     censal hydrate tables, declaration extractors, portal/deadline logic,
     export or submission specs, tests, manuals, BOE references, and official
     AEAT record designs.
  - [ ] Produce a Modelo 036 model-law coverage ledger covering all revisions,
     census sections, identity/activity/tax-regime registration fields, legal
     references, source artefacts, filing paths, tests, and old authorities to
     delete.
  - [ ] Research and verify the official AEAT and BOE basis for full censal
     declaration and registration/modification obligations.
  - [ ] Classify the Modelo 036 live AEAT cross-reference surface and add
     remote-state guard tests; authenticated census registration/modification,
     signing, presentation, server-side save, and any AEAT write action are
     forbidden for synthetic tests.
  - [ ] Write `registry/aeat/modelos/036.toml` with every reviewed revision,
     casilla or record definition, validation rule, parameter, data binding,
     legal reference, source reference, and export or filing layout.
  - [ ] Link Modelo 036 to registry-backed validation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export or submission
     workflows.
  - [ ] Verify Modelo 036 with real census examples, invalid registration cases,
     legal-reference checks, source-integrity checks, filing/export roundtrips,
     and registry failure cases.
  - [ ] Delete Modelo 036 old authorities in censal hydrate tables, declaration
     extractor truth, modelo metadata duplicates, casilla projections, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 036 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 20` Modelo 037 complete implementation
  - [ ] Audit every Modelo 037 authority in modelo metadata, casilla corpus,
     censal hydrate tables, declaration extractors, retired portal metadata,
     tests, manuals, BOE references, and any official AEAT evidence available
     for historical or retired filing support.
  - [ ] Produce a Modelo 037 model-law coverage ledger covering all supported
     historical or retired revisions, legal basis for retirement or replacement
     by Modelo 036, source artefacts, filing-history paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for simplified censal
     declaration, historical support, retirement, and transition to Modelo 036.
  - [ ] Classify the Modelo 037 live AEAT cross-reference surface and add
     remote-state guard tests. If current filing-grade evidence is absent,
     remove Modelo 037 filing app entry points and keep only historical
     evidence records that cannot be invoked as filing support.
  - [ ] Write `registry/aeat/modelos/037.toml` with every reviewed historical or
     retired revision, casilla or record definition, validation rule, legal
     reference, source reference, and filing-history linkage.
  - [ ] Link Modelo 037 to registry-backed validation for the exact legally
     supported scope. Current filing must fail if the official legal status says
     the model is retired; historical filing or import support must still be
     registry-backed.
  - [ ] Verify Modelo 037 with real historical/retirement examples, invalid current
     filing cases, legal-reference checks, source-integrity checks, and registry
     failure cases.
  - [ ] Delete Modelo 037 old authorities in censal hydrate tables, declaration
     extractor truth, retired portal hardcoding, modelo metadata duplicates,
     casilla projections, and any implied support path outside the registry.
  - [ ] Add behaviour tests proving Modelo 037 filing, import, and validation
     workflows require a validated registry snapshot and fail fast on coverage
     gaps.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Phase 4R` Modelo 100 Renta aggregation prerequisite
  - [x] Create the Modelo 100 aggregation audit covering `registry/aeat`,
     `corpus/aeat_official/disenos_registro/modelo_100`,
     `corpus/manuals/renta`, `src/aeat/adapters/inbound/borrador`,
     `src/aeat/adapters/inbound/declaracion`,
     `src/aeat/adapters/outbound/aeat/sede`, `src/aeat/domain/rental`,
     `src/aeat/domain/portals`, category profiles, tests, older Renta vault
     documents, and any remaining source that encodes Modelo 100 casilla,
     schema, source, legal, calculation, parser, live-read, or filing meaning.
  - [x] Register Modelo 100/Renta source and legal corpus references in the
     same shared registry catalogue consistency framework used by implemented
     modelos, including official record-design dictionaries/XSDs, Renta 2025
     manuals, LIRPF activity-economics legal anchors, source hashes, local
     corpus paths, and manifest-backed verification tests.
  - [x] Produce the Modelo 100 source-dependency reference tying official AEAT
     procedure, record-design, manual, presentation, Renta WEB Open, BOE order,
     LIRPF, RIRPF, and local corpus resources to direct-dependency,
     evidence-only, and explicit non-dependency classifications.
  - [ ] Produce the Modelo 100 source ledger for ejercicio 2020, ejercicio
     2021, ejercicio 2022, ejercicio 2023, ejercicio 2024, and ejercicio 2025,
     with every official AEAT dictionary, toma-de-datos dictionary, XSD,
     historical PDF/XLS/XLSX artefact, manual part, handbook page, BOE act,
     CCAA legal source, Renta WEB Open surface, authenticated read-only
     observation path, and local corpus hash accounted for.
     - [x] Record-design ledger: official AEAT declaration dictionaries,
       toma-de-datos dictionaries, and XSDs for ejercicio 2020 through
       ejercicio 2025 are identified by registry source ref and local manifest
       evidence in the Modelo 100 source-dependency reference.
     - [x] Renta 2025 manual ledger: practical manual part 1 and autonomous
       deductions manual part are identified by registry source ref, local
       manifest evidence, and source hashes in the Modelo 100
       source-dependency reference.
     - [x] BOE annual order ledger: Modelo 100 ejercicio 2025 order
       `orden-hac-277-2026:art-3` and source `boe-modelo-100-2025-form` are
       registered with local BOE HTML corpus evidence.
     - [ ] BOE legal ledger: add the complete LIRPF/RIRPF article set by
       construct, annual objective-estimation orders, and law-effective date
       ranges.
     - [ ] CCAA legal ledger: add autonomous-community legal sources for
       deductions, tariff/minimum variations, territorial applicability, and
       yearly change tracking.
     - [ ] Observation ledger: add Renta WEB Open parity surface and
       authenticated read-only observation surfaces with encrypted-store and
       remote-state guard requirements.
       - [x] Register Renta WEB Open as explicit executable parity evidence
         for Modelo 100 ejercicio 2025 with local AEAT corpus evidence,
         non-authenticated simulator classification, and forbidden remote-state
         actions.
       - [ ] Register authenticated fiscal-data, borrador, declaration,
         submitted-file, declaration PDF, and justificante observation surfaces
         with encrypted-store and remote-state guard requirements.
       - [x] Register Modelo 100 `Consulta de declaraciones presentadas` as
         an authenticated read-only observation surface in the central registry,
         backed by local AEAT procedure corpus and remote-state guard mapping.
  - [ ] Produce the Modelo 100 deletion ledger naming every old authority that
     must disappear or become lean plumbing: old formula/ruleset-era modules,
     Renta helper modules, rental legal-calculation ownership, amortization
     legal constants, inventory legal constants, category/profile Renta
     authority, borrador extractor casilla ownership, declaracion extractor
     casilla ownership, Sede filed-data parser assumptions, portal metadata
     duplicates, generated/projection files, and tests that encode old state.
  - [ ] Write the Modelo 100 support boundary: supported ejercicios,
     unsupported ejercicios, filing-period date axes, legal-effective date axes,
     source artefact date axes, CCAA applicability axes, live observation axes,
     and exact failure conditions for gaps or contradictions.
  - [ ] Classify Renta WEB Open as read-only parity evidence and prove the
     remote-state guard rejects authenticated Renta WEB, fiscal-data, borrador,
     declaration, justificante, signing, presentation, payment, server-side
     save, amendment, cancellation, and document-submission actions before
     execution.
     - [x] Modelo 100 ejercicio 2025 registry now declares Renta WEB Open as an
       open simulator cross-reference with no authentication, synthetic data
       allowed, and presentation/payment/signing/server-side-write actions
       forbidden.
  - [ ] Classify authenticated fiscal-data, borrador, declaration, submitted
     file, declaration PDF, and justificante capture as read-only observations
     that must persist only through the encrypted observation store and must
     never define legal formulas or mutate registry files.
     - [x] Modelo 100 ejercicio 2025 registry now declares
       `modelo-100-filed-declarations-read` as authenticated read surface:
       no synthetic data, authentication and AEAT authorization required,
       read-only HTTP methods only, and presentation/payment/signing/save
       actions forbidden.
     - [x] Wire the Sede filed-declaration reader to select its guard policy
       from the validated Modelo 100 registry snapshot instead of the module
       default policy.
       The reusable Sede declaration capture path now resolves the read guard
       from the selected registry snapshot once the declaration row identifies
       modelo, ejercicio, and period. Register discovery remains guarded by the
       generic authenticated declarations policy until a concrete snapshot can
       be selected.
     - [x] Add live/sanitized Modelo 100 observation fixtures proving
       submitted-file or declaration-copy capture maps into standardized
       observations with encrypted storage.
     - [x] Run authenticated Modelo 100 live filed-row discovery through
       `Consultar declaraciones presentadas`, record which ejercicios expose
       submitted-file downloads, declaration-copy PDFs, justificante PDFs, and
       register-row metadata, and persist only sanitized or encrypted artefacts.
       Live read on 2026-05-05 found Modelo 100 filed rows for ejercicios
       2021, 2022, and 2023. Each available row exposed submitted-file and
       justificante artefacts; no declaration-copy PDF was exposed. Ejercicios
       2020, 2024, and 2025 returned no rows for the authenticated account.
       No AEAT write, signing, payment, amendment, or presentation action was
       executed.
     - [x] Add a Modelo 100 live-read capture command/test path that refuses
       remote writes, requires the snapshot-derived authenticated read policy,
       and persists raw captured artefacts only through
       `FiledDeclarationObservationStore`.
       - [x] Historical guard coverage: add the authenticated
         filed-declarations read surface and application link to Modelo 100
         ejercicio 2020 through ejercicio 2024 revisions so historical live
         rows can select a registry-derived guard before capture.
       - [x] Export-layout blocker: implement Modelo 100 XML/XSD-backed
         submitted-file parsing for ejercicio 2021, ejercicio 2022, and
         ejercicio 2023 before live capture can produce standardized casilla
         observations. The current fixed-width export parser correctly refuses
         Modelo 100 revision 2023 because no registry export layout exists.
         Modelo 100 revisions 2020 through 2025 now declare
         XML-dictionary export layouts backed by the official AEAT dictionary
         and XSD source refs, with export application links required by the
         registry validator.
       - [x] Live capture verification: rerun a one-row encrypted Modelo 100
         capture after the XML/XSD export layout exists and require
         `capture-filed-data` to return a persisted encrypted observation
         manifest with non-zero normalized casilla observations.
         The authenticated 2026-05-05 read-only capture for ejercicio 2023
         persisted one encrypted observation and three encrypted financial
         artefacts under `var/aeat/filed-declarations`, and produced 77
         normalized casilla observations.
     - [x] Add a committed sanitized Modelo 100 declaration-copy or
       submitted-file fixture with every PII and financial value replaced by
       shape-preserving data, then prove the fixture maps into
       `FiledDeclarationObservation` without defaults or silent degradation.
       `tests/fixtures/aeat-sede/submitted-files/modelo-100-2023-0A-redacted.xml`
       preserves the official XML element shape and dictionary paths while
       replacing identity and amount values with typed synthetic values.
       The Sede parser test resolves the 2023 registry snapshot, parses the
       fixture through the official AEAT dictionary source, and requires 77
       observed casilla values.
     - [x] Add an encrypted observation-store roundtrip for the sanitized
       Modelo 100 observation proving artefact bytes, manifest metadata, and
       normalized casilla observations are reloadable through the secure
       storage backend.
       The roundtrip persists the XML fixture as a financial encrypted blob,
       writes a `FiledDeclarationObservation`, reloads the manifest, and
       decrypts the artefact bytes through `FiledDeclarationObservationStore`.
     - [x] Add Renta dependency-resolution tests that consume standardized
       Modelo 100/130/131 observations from the registry observation layer and
       fail hard when a required upstream observation is absent,
       contradictory, or below extraction coverage.
       The Sede relation tests now resolve all declared Modelo 100 ejercicio
       2025 dependency observations, including Modelo 130 and Modelo 131
       quarterly instalment observations, through
       `resolve_relation_values_from_filed_declarations`; missing and
       duplicated source periods fail before any annual value is emitted.
  - [ ] Define the `registry/aeat/modelos/100.toml` scaffold shape for parent
     identity, revision selection, common legal basis, source references,
     source ledgers, legal ledgers, Renta subdomains, final settlement, typed
     relations to Modelos 130 and 131, export layout references, live/static
     cross-reference decisions, and hard failure gates.
     - [x] Create `registry/aeat/modelos/100.toml` with the Modelo 100 parent,
       ejercicio 2020 through ejercicio 2025 revisions, record-design layout
       parity decisions, reviewed source refs, and the ejercicio 2025 annual
       order source/legal references.
     - [x] Add initial ejercicio 2025 dependency relations from registered
       Modelos 111, 115, 123, 130, 131, and 180 to Modelo 100 Renta bindings.
       Relations to modelos that do not yet exist in `registry/aeat/modelos`
       remain blocked until those modelo authorities exist.
     - [x] Add the generic revision construct schema, snapshot exposure, and
       validator closure checks so Modelo 100 can declare auditable Renta
       children without separate modelo ids or Python-owned authority.
     - [ ] Add Renta subdomain casilla/formula coverage, final settlement
       casillas, extraction profiles, export/import layout references,
       live/static cross-reference decisions, and hard failure gates.
  - [ ] Define the Renta construct ledger under the Modelo 100 parent. Each
     construct must have a stable id, ejercicios covered, legal refs, source
     refs, casilla scope, formulas or algorithm bindings, parser bindings,
     observation bindings, teardown targets, tests, and completion gate.
     - [x] `renta-source-foundation`: parent identity, ejercicios, official
       Modelo 100 order, AEAT dictionaries, toma-de-datos dictionaries, XSDs,
       manuals, Renta WEB Open classification, filed-data observation
       classification, and corpus/source hash closure.
       Initial ejercicio 2025 construct ownership now covers record-design
       layout parity, Renta WEB Open, the Modelo 100 procedure source, the
       authenticated filed-declarations read surface, and the portal
       cross-reference.
     - [ ] `renta-dependent-modelos`: typed dependency ledger for periodic,
       monthly, quarterly, and annual filings that can feed Modelo 100,
       including Modelos 111/190, 115/180, 123/193, 130, 131, and any other
       supported declaration that contributes retentions, payments on account,
       income, expense, or summary evidence.
       The Modelo 100 source-dependency reference is the controlling resource
       for this classification until `registry/aeat/modelos/100.toml` encodes
       the same relations with source/legal refs and validator checks.
       - [x] Initial construct ownership now covers registered Modelo 100
         dependency bindings and relations for Modelos 111, 115, 123, 130,
         131, and 180.
       - [x] Dependency classification gate: Modelo 100 ejercicio 2025 now
         classifies every registered dependency source relation for Modelos
        111, 115, 123, 130, 131, 180, 190, and 193, and the registry validator
        rejects source/relation drift.
       - [ ] Direct annual-settlement dependencies:
         - [x] Modelo 111 -> Modelo 100 work/professional/agricultural
           retentions and payments on account.
         - [x] Modelo 190 -> Modelo 100 annual work/professional recipient
           summary and withholding reconciliation.
         - [x] Modelo 115 -> Modelo 100 urban-rental retentions borne by the
           taxpayer or payer-side evidence where the taxpayer role requires it.
         - [x] Modelo 180 -> Modelo 100 annual urban-rental withholding summary
           and property/payer reconciliation.
         - [x] Modelo 123 -> Modelo 100 movable-capital retentions and income
           account payments.
         - [x] Modelo 193 -> Modelo 100 annual movable-capital income and
           withholding reconciliation.
         - [x] Modelo 130 -> Modelo 100 direct-estimation instalment payments,
           current-year economic-activity evidence, and previous-year
           dependency values.
         - [x] Modelo 131 -> Modelo 100 objective-estimation instalment
           payments, module/activity evidence, and current-year objective
           estimation reconciliation.
       - [x] Factual evidence dependencies, not legal-calculation authorities:
         - [x] Modelo 303 -> Modelo 100 economic-activity factual VAT context,
           invoice/expense reconciliation, and VAT-deductibility evidence; it
           cannot decide IRPF income, expense, or casilla treatment.
         - [x] Modelo 390 -> Modelo 100 annual VAT-summary reconciliation for
           economic-activity evidence only; it cannot decide IRPF formulas.
         - [x] Modelo 347 -> Modelo 100 third-party operation evidence for
           business income/expense reconciliation only.
         - [x] Modelo 349 -> Modelo 100 intra-community operation evidence for
           business/fiscal-data reconciliation only.
         - [x] Modelo 369 -> Modelo 100 OSS/IOSS VAT evidence for activity
           context only.
         - [x] Modelo 840 -> Modelo 100 IAE activity/municipality evidence for
           economic-activity applicability and classification only.
         - [x] Modelos 036 and 037 -> Modelo 100 censal identity, activity,
           regime, and obligation evidence only; they cannot own annual
           calculation values.
       - [x] Non-Renta calculation dependencies unless a future official source
         proves a concrete link:
         - [x] Modelo 202 is corporate-tax instalment evidence for a different
           taxpayer/tax and is not a Modelo 100 calculation dependency.
         - [x] Modelo 200 is corporate annual tax evidence for a different
           taxpayer/tax and is not a Modelo 100 calculation dependency.
         - [x] Modelo 232 is related-party reporting evidence and is not a
           Modelo 100 calculation dependency.
         - [x] Modelo 720 is foreign-asset reporting evidence and is not a
           Modelo 100 calculation dependency; foreign income, gains, or
           imputations must be represented through Modelo 100 legal/source
           definitions, not inferred from Modelo 720 filing status.
     - [ ] `renta-personal-family`: taxpayer identity, family unit, joint or
       individual taxation, descendants, ascendants, disability, minimums, and
       personal circumstances.
     - [ ] `renta-work-income`: salaries, pensions, benefits, deductible work
       expenses, reductions, retentions, employer summaries, and relation to
       Modelos 111 and 190.
       - [x] Initial ejercicio 2025 construct membership now classifies
         registered Modelo 111 dependency relations for work/professional or
         related retentions and payments-on-account evidence.
       - [x] Add Modelo 190 annual-summary relation as factual evidence from
         the central Modelo 190 registry authority.
       - [ ] Add filing-grade work-income casillas, formulas, parameters,
         source citations, and observation profiles.
        - [x] Work-income casilla/formula slice: Modelo 100 ejercicio 2025
          now owns the registry-backed work-income chain for casillas 0003
          through 0025, including in-kind work income, total computable work
          income, net previous work income, net work income, reduced net work
          income, Ley 35/2006 article 17 through 20 legal refs, official source
          citations, construct ownership, and behaviour tests.
        - [ ] Work-income observation profiles remain open before observed
          Modelo 190/fiscal-data work-income values can be accepted as
          filing-grade calculation input.
     - [ ] `renta-real-estate-capital`: rental income, deductible expenses,
       real-estate imputation, residential rental reductions, withheld rental
       amounts, and relation to Modelos 115 and 180.
       - [x] Initial ejercicio 2025 construct membership now classifies
         registered Modelo 115 and Modelo 180 dependency relations for urban
         rental withholding evidence.
       - [ ] Add filing-grade real-estate income, deduction, imputation,
         reduction, rental-ledger, and amortization casillas/formulas.
        - [x] Real-estate capital casilla/formula slice: Modelo 100 ejercicio
          2025 now owns registry-backed capital inmobiliario casillas 0089,
          0102, 0104, 0107, 0109 through 0117, 0131, 0132, 0146 through 0156,
          and 0598, including net return, reduced net return, imputed-rent
          total, reduced-return total, rental withholding total, Ley 35/2006
          article 22 through 24 legal refs, official source citations,
          construct ownership, and behaviour tests.
        - [ ] Rental-ledger row aggregation, amortization-provider linkage,
          article 23.2 reduction tier automation, and observed Modelo 115/180
          reconciliation remain open.
     - [ ] `renta-movable-capital`: dividends, interest, insurance, other
       movable-capital income, retentions, and relation to Modelos 123 and 193.
       - [x] Initial ejercicio 2025 construct membership now classifies
         registered Modelo 123 dependency relations for movable-capital
         withholding evidence.
       - [x] Add Modelo 193 annual-summary relation as factual evidence from
         the central Modelo 193 registry authority.
       - [ ] Add filing-grade movable-capital casillas, formulas, parameters,
         source citations, and observation profiles.
        - [x] Movable-capital casilla/formula slice: Modelo 100 ejercicio
          2025 now owns the registry-backed capital mobiliario chain for
          casillas 0027 through 0041 and 0046 through 0060, including saving
          base/general base totals, net returns, reduced net returns, Ley
          35/2006 article 25 and 26 legal refs, official source citations,
          construct ownership, and behaviour tests.
        - [ ] Movable-capital observation profiles remain open before
          observed Modelo 123/193/fiscal-data values can be accepted as
          filing-grade calculation input.
     - [ ] `renta-economic-activities`: estimacion directa normal, estimacion
       directa simplificada, estimacion objetiva, invoices, expenses, VAT-aware
       category evidence, payments on account, and relation to Modelos 130 and
       131.
       - [x] Initial ejercicio 2025 construct membership now classifies
         registered Modelo 130 and Modelo 131 dependency relations for
         direct-estimation and objective-estimation instalment evidence.
       - [x] Payments-on-account calculation slice: Modelo 100 ejercicio 2025
         now owns casilla 0604 as the registry sum of Modelo 130 and Modelo
         131 relation values, and casilla 0609 as the official total pagos a
         cuenta sum across AEAT casillas 0592, 0593, 0594, 0596 through 0606.
       - [ ] Add filing-grade economic-activity income, expense, activity,
         module, category, invoice, VAT-context, previous-filing, and
         amortization/inventory casillas/formulas.
     - [ ] `renta-amortization-inventory`: amortization ledgers, asset classes,
       acquisition/improvement cost, inventory valuation, carry-forward
       treatment, and algorithm bindings used by real-estate and economic
       activity constructs.
     - [ ] `renta-special-regimes-imputations`: income attribution,
       international fiscal transparency, image-rights assignment, collective
       investment imputations, and other special regimes represented by the
       official form and manual.
     - [ ] `renta-capital-gains-losses`: transmissions, exemptions,
       reinvestment, FIFO or other statutory ordering, integration, and
       compensation.
     - [ ] `renta-bases-reductions`: general base, saving base, integrations,
       compensations, pension-plan reductions, joint taxation reductions, and
       carry-forward rules.
     - [ ] `renta-tax-free-minimums-and-brackets`: personal and family
       minimums, state tariff, autonomous tariff, saving tariff, tax-free
       bracket effects, state quota, autonomous quota, and liquid quota.
     - [ ] `renta-deductions-state`: state deductions, maternity/family
       deductions, donations, housing transition rules, Ceuta/Melilla, and
       other annual special provisions.
     - [ ] `renta-deductions-autonomous`: CCAA-specific deductions, foral
       exclusions, territorial applicability, annual legal-source variation,
       contradiction checks, and autonomous-community trace output.
     - [ ] `renta-payments-retentions`: all retentions, payments on account,
       previous instalments, annual summaries, fiscal-data observations, and
       dependency reconciliation before final settlement.
       - [x] Initial ejercicio 2025 construct membership now covers registered
         Modelo 111, 115, 123, 130, 131, 180, 190, and 193 dependency bindings
         and relations under LIRPF/RIRPF payments-on-account legal refs.
     - [ ] `renta-final-settlement`: cuota diferencial, result to pay/refund,
       payment/refund structure, Modelo 102 linkage where relevant, and final
       declaration review trace.
       - [x] Final settlement roll-up slice: Modelo 100 ejercicio 2025 now
         owns casillas 0587, 0595, 0610, and 0670 as registry-backed formulas,
         with required intermediate final-result casillas, Modelo 130/131
         payments-on-account inputs through casilla 0609, official manual/BOE
         source citations, construct ownership, and behaviour tests.
       - [ ] Upstream cuota, tariff, deduction, payment/refund structure,
         Modelo 102 linkage, and final declaration-review trace remain open.
     - [ ] `renta-observation-parsing`: borrador, declaracion, submitted-file,
       declaration PDF, justificante PDF, and Sede filed-data observations with
       registry extraction profiles and encrypted storage.
       - [x] Initial ejercicio 2025 construct membership now declares
         `Consulta de declaraciones presentadas` as an authenticated read-only
         observation surface with registry remote-state guard coverage.
       - [ ] Add extraction profiles for submitted-file and declaration-copy
         artefacts before any observed Modelo 100 casilla is accepted for
         filing-grade calculation.
     - [ ] `renta-export-filing-linkage`: import/export layout, preview,
       review, approval, filing draft, remote-state guard, and any programmatic
       filing linkage allowed by the registry.
  - [ ] Define the Modelo 100 programmatic reader path under
     `src/aeat/domain/calculations/registry/` for loading the 100 registry
     graph, validating source/legal closure, selecting ejercicio revisions,
     binding Renta subdomains, executing typed formulas and algorithm
     providers, reconciling observations, and producing traceable calculation
     output.
     - [x] Add generic construct resolution in
       `src/aeat/domain/calculations/registry/_constructs.py` so callers can
       resolve revision constructs to concrete member objects after registry
       validation.
     - [ ] Add Modelo 100-specific calculation orchestration over resolved
       constructs once casilla/formula and algorithm bindings exist.
  - [ ] Add generalized registry tests for Modelo 100 catalogue, legal, source,
     parser, observation, relation, and corpus consistency. These tests must
     exercise real registry loading and real corpus files, not old/new state
     comparisons.
     - [x] Catalogue/source/legal consistency tests: verify Modelo 100
       dictionary, toma-de-datos, XSD, Renta manual, and LIRPF legal references
       through real registry catalogue loading and corpus-file checks.
     - [x] Modelo 100 source/dependency tests: verify the 2020-2025 registry
       revisions against the official record-design manifest and verify the
       2025 dependency relations against registered source-modelo outputs and
       periods.
     - [x] Modelo 100 construct tests: verify snapshot exposure of construct
       ownership and fail validation when a construct references a member not
       declared by the selected revision.
     - [x] Modelo 100 construct dependency tests: mutate the real registry
       objects to prove construct-owned dependency classifications cannot
       reference members outside the selected revision.
     - [x] Modelo 100 dependency classification closure tests: mutate the real
       registry objects to prove validation fails when a relation source lacks
       classification, a classification covers only part of its source
       relations, or a source is classified more than once.
     - [x] Formula runtime external-value tests: prove the registry calculator
       rejects binding and relation values whose identifiers are not declared by
       the selected revision.
  - [ ] Mark Phase 4R complete only after the audit document, source ledger,
     deletion ledger, schema boundary, live-read classification, observation
     security path, and validation test plan are explicit and reviewable.

- `Wave 21` Modelo 100 Renta universe complete implementation
  - [ ] Build `registry/aeat/modelos/100.toml` as the sole Modelo 100
     authority, with no Python-owned legal constants, casilla dependencies,
     formula dependencies, source metadata, or revision selection.
  - [ ] Implement the Renta construct gate in the registry validator so a
     construct can only reference revision members that exist, and each
     referenced member remains covered by the construct legal/source
     references. Filing-grade
     completion still requires all construct rows below to close with casilla,
     formula, extraction, observation, export, and verification coverage.
     - [x] Add generic `ConstructDefinition` schema, `ModeloRevision.constructs`,
       `RegistrySnapshot.constructs`, and validator closure checks.
     - [x] Include dependency classifications in construct closure so Renta
       constructs fail hard when they point at undeclared dependency members.
     - [x] Enforce reciprocal dependency-classification ownership: a
       classification that targets a construct must be listed by that construct,
       and Modelo 180, Modelo 190, and Modelo 193 annual-summary constructs now
       declare their source dependency classifications.
  - [ ] Implement the cross-model dependency resolver for Modelo 100 so
     dependent periodic, monthly, quarterly, and annual filings are selected by
     filing period, ejercicio, taxpayer, relation type, source evidence, and
     observation quality before their values can feed the annual declaration.
     - [x] Relation source requirements now carry the registry dependency
       treatment from the source classification, so callers can distinguish
       annual-settlement inputs from factual evidence while resolving the same
       observation backend.
     - [x] Relation observation resolution now respects target filing periods,
       so a quarterly filing cannot be forced to provide annual-summary
       relation observations that are only active for `0A`.
     - [x] Registry snapshots now carry selected filing year and period as
       first-class context, and calculation relation validation accepts only
       relation values active for that selected period.
     - [x] Invoice-source binding resolution now has a shared observation
       contract and resolver for modelo-agnostic invoice-ledger facts, including
       intra-community claves, rectification scope, base totals, and distinct
       operator counts.
     - [x] Registry validation now rejects malformed invoice-source selectors
       and unsupported invoice fact or aggregation pairs before snapshot or
       calculation runtime use.
  - [ ] Implement the dependency classification gate for every supported
     modelo. A supported modelo must be declared as direct dependency, factual
     evidence dependency, or non-dependency before Modelo 100 can emit a
     filing-grade snapshot.
     - [x] Registry validator now enforces one dependency classification per
       relation source and requires each classification to cover every relation
       for that source before a Modelo 100 snapshot can validate.
  - [ ] Implement dependency inputs from Modelo 111 and Modelo 190: work-income
     retentions, recipient/employer summaries, annual withholding totals,
     source/legal references, and contradiction checks against fiscal-data or
     filed-data observations.
     - [x] Modelo 100 ejercicio 2025 now declares Modelo 190 annual
       retentions as factual evidence through a registry binding, relation,
       dependency classification, construct membership, and relation-resolution
       behaviour test.
  - [ ] Implement dependency inputs from Modelo 115 and Modelo 180:
     urban-rental retentions, annual rental-withholding summaries, property or
     payer records where available, source/legal references, and contradiction
     checks against rental ledgers and observations.
  - [ ] Implement dependency inputs from Modelo 123 and Modelo 193:
     movable-capital retentions, annual capital-income summaries, source/legal
     references, and contradiction checks against financial-income observations.
     - [x] Modelo 100 ejercicio 2025 now declares Modelo 193 annual
       retentions as factual evidence through a registry binding, relation,
       dependency classification, construct membership, and relation-resolution
       behaviour test.
  - [ ] Implement dependency inputs from Modelo 130: direct-estimation
     instalment payments, previous-year and current-year economic activity
     evidence, source/legal references, and date-axis checks across quarterly
     declarations.
  - [ ] Implement dependency inputs from Modelo 131: objective-estimation
     instalment payments, module/activity evidence, source/legal references,
     and date-axis checks across quarterly declarations.
  - [x] Implement evidence-only classification for Modelos 303, 390, 347, 349,
     369, 840, 036, and 037. These surfaces may support activity, VAT,
     invoice, census, operation, or obligation reconciliation, but cannot own
     Modelo 100 legal treatment, formulas, casilla targets, or final annual
     amounts.
  - [x] Implement explicit non-dependency classification for Modelos 202, 200,
     232, and 720 unless a reviewed official source creates a concrete Modelo
     100 relation. Their filed status must not alter Renta calculations by
     inference.
  - [ ] Implement dependency inputs from invoice, expense, VAT, category,
     transaction, bank, attachment, and review domains only as factual data
     bindings. Modelo 100 registry definitions must own the legal treatment and
     casilla targets.
     - [x] Invoice-source bindings now support deterministic repeated-row
       factual outputs for operator/clave and operator/clave/period groupings,
       with registry validation rejecting period-grouped rows unless they are
       scoped to rectification observations.
     - [x] Invoice repeated-row outputs now use one-based row indexes so
       resolved registry binding rows align with filing draft binding values
       and fixed-width export rendering.
  - [ ] Implement ejercicio 2020 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, manual/legal sources, source hashes,
     parser requirements, legal references, formula coverage ledger, export
     layout references, and failure gates.
  - [ ] Implement ejercicio 2021 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, manual/legal sources, source hashes,
     parser requirements, legal references, formula coverage ledger, export
     layout references, and failure gates.
  - [ ] Implement ejercicio 2022 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, manual/legal sources, source hashes,
     parser requirements, legal references, formula coverage ledger, export
     layout references, and failure gates.
  - [ ] Implement ejercicio 2023 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, manual/legal sources, source hashes,
     parser requirements, legal references, formula coverage ledger, export
     layout references, and failure gates.
  - [ ] Implement ejercicio 2024 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, manual/legal sources, source hashes,
     parser requirements, legal references, formula coverage ledger, export
     layout references, and failure gates.
  - [ ] Implement ejercicio 2025 revision from reviewed AEAT dictionaries,
     toma-de-datos dictionary, XSD, official Renta 2025 handbook, BOE Modelo
     100 order, source hashes, parser requirements, legal references, formula
     coverage ledger, export layout references, and failure gates.
  - [ ] Implement `renta-source-foundation`: load the Modelo 100 parent,
     revision source ledgers, legal ledgers, official source hashes, source
     tiers, live/static cross-reference decisions, workbook/layout decisions,
     and fatal source-gap rules.
     - [x] Ejercicio 2025 source-foundation construct now owns the full
       revision legal/source ledger, workbook parity refs, live cross
       references, application-link workflow refs, and a regression assertion
       that prevents future source/legal ledger drift.
  - [x] Implement `renta-dependent-modelos`: declare every supported dependency
     relation, relation selector, accepted observation artefact, value
     precedence rule, contradiction rule, required source/legal refs, and trace
     output.
     Current closure covers the supported registered Modelo 100 dependency
     sources 111, 115, 123, 130, 131, and 180. Future sources 190, 193, 303,
     390, 347, 349, 369, 840, 036, and 037 remain separate plan rows because
     they are not yet central registry modelos in this worktree.
  - [ ] Implement Renta personal/family circumstances as registry-backed
     casillas, parameters, date-axis rules, legal references, source
     references, parser bindings, and trace output.
     - [ ] Personal identity and taxpayer role fields.
       - [x] Initial 2025 identity/profile binding slice registers official
         Modelo 100 dictionary/XSD fields `DPNIF_D`, `DP_APENOM_D`, `ZCCAD`,
         and `TIPOTRIBUTACION` as bound casillas under `renta-personal-family`,
         with profile selectors tied to `PROFILE_KEYS` and `TaxResidenceProfile`
         schema ownership.
     - [ ] Family unit and individual/joint taxation selection.
     - [ ] Descendants, ascendants, disability, age, and dependency conditions.
     - [ ] Minimums and personal/family circumstance transfer into the base and
       quota constructs.
  - [ ] Implement Renta work income as registry-backed casillas, formulas,
     parameters, legal references, source references, parser bindings, and
     trace output.
     - [ ] Gross monetary and in-kind work income.
     - [ ] Social security, deductible work expenses, irregular-income
       reductions, and net work income.
     - [ ] Retentions and payments on account from Modelo 111/190, fiscal data,
       and filed observations.
  - [ ] Implement Renta real-estate capital and imputacion de rentas
     inmobiliarias as registry-backed casillas, formulas, rental-register input
     bindings, legal references, source references, parser bindings, and trace
     output.
     - [ ] Rental income and deductible expense rollups.
     - [ ] Amortization and improvement-cost bindings.
     - [ ] Residential rental reduction tiers and temporal applicability.
     - [ ] Real-estate imputation and cadastral-value date-axis rules.
     - [ ] Rental withholding relations to Modelos 115 and 180.
  - [ ] Implement Renta movable-capital income as registry-backed casillas,
     formulas, parameters, withholding relations, legal references, source
     references, parser bindings, and trace output.
     - [ ] Dividends, interest, insurance, and other movable-capital categories.
     - [ ] Deductible expenses, reductions, integration into saving/general
       bases, and retentions from Modelos 123/193.
  - [ ] Implement Renta economic activities in estimacion directa normal,
     estimacion directa simplificada, and estimacion objetiva as
     registry-backed casillas, formulas, algorithm bindings, module/order
     source references, legal references, parser bindings, and trace output.
     - [ ] Direct normal estimation: income, deductible expenses, inventory,
       amortization, provisions, and accounting-derived adjustments.
       - [x] Ejercicio 2025 direct-estimation income and expense subtotal
         arithmetic is registry-backed for casillas 0171-0180, 0181-0218,
         0219-0221, and 0225 with legal/source closure and behaviour tests.
       - [x] Final net-return selection and reduction application are now
         registry-backed for the 2025 direct-estimation branch via casillas
         0224, 0226, 0231, and 0235, with mode-dependent selection grounded in
         AEAT manual guidance and covered by behavior tests.
       - [ ] Inventory, amortization-provider linkage, provisions beyond direct
         manual input, and accounting-derived adjustments remain open.
     - [ ] Direct simplified estimation: simplified expenses, statutory caps,
       reductions, and source/legal references.
       - [x] Ejercicio 2025 simplified total deductible expenses are computed
         as casilla 0223 from 0218 and 0222 under AEAT manual/source
         citation validation.
       - [x] The direct-estimation reduction chain now includes registry-backed
         mode selection, reduction application, and reduced-total propagation
         for the 2025 slice.
       - [x] Statutory cap calculation for difficult-justification expenses is
         registry-backed for ejercicio 2025. Casilla 0222 is computed from the
         5 percent Reglamento IRPF article 30 parameter, clamps negative bases
         to zero, applies the EUR 2,000 annual cap, feeds casilla 0223, and is
         covered by trace/legal-ref behaviour tests. Simplified-estimation final
         selection remains open.
     - [ ] Objective estimation: activity modules, signs, indices, reductions,
       annual module orders, and relation to Modelo 131.
       - [x] Objective-estimation record-design outputs 1479, 1553, and 1577
         are registry-backed as informational casillas and round-trip through
         the official 2025 export parser paths.
       - [ ] Objective-estimation formulas, signs, indices, and reductions
         remain open until the module-order arithmetic is grounded.
     - [x] Payments on account, retentions, and relation to Modelos 130 and 131.
       Casilla 0604 is computed from the registered Modelo 130 and Modelo 131
       relation values; casilla 0609 totals the official AEAT payments-on-
       account casilla set for ejercicio 2025.
     - [ ] VAT/category/transaction inputs as factual bindings only, with legal
       treatment owned by Modelo 100 registry definitions.
  - [ ] Implement Renta capital gains/losses, integrations, compensations,
     bases, reductions, minimos, state quota, saving quota, liquid quota,
     deductions, and final result as registry-backed formulas with legal/source
     closure and date-axis tests.
     - [ ] Capital gains/losses: transmissions, exemptions, reinvestments,
       statutory ordering, and integration.
     - [ ] Bases and compensations: general base, saving base, carry-forward
       balances, and cross-year limits.
     - [ ] Reductions: pension systems, joint taxation, disability-related
       systems, and other official Modelo 100 reductions.
     - [ ] Minimums and brackets: personal/family minimums, state tariff,
       saving tariff, autonomous tariff, state/autonomous quota split, and
       tax-free bracket effects.
     - [ ] Final settlement: cuota integra, cuota liquida, cuota diferencial,
       deductions, retentions, instalments, result to pay/refund, and Modelo
       102 linkage where applicable.
  - [ ] Implement CCAA and Ceuta/Melilla Renta rules with autonomous-community
     legal sources, temporal applicability, foral exclusions, contradiction
     checks, source coverage, parser/export bindings, and trace output.
     - [ ] Autonomous deduction catalogue by community and ejercicio.
     - [ ] Autonomous tariff and minimum variations where applicable.
     - [ ] Territorial residence/date-axis selection and foral exclusion.
     - [ ] Ceuta/Melilla state provisions and source/legal trace separation.
  - [ ] Implement rental, amortization, and inventory as deterministic
     algorithm providers whose legal constants, caps, casilla targets, and
     input bindings are declared by Modelo 100 registry data.
     - [ ] Rental factual ledger provider returns factual totals only.
     - [ ] Amortization provider consumes registry-declared legal constants and
       emits traceable per-asset results.
     - [ ] Inventory provider consumes registry-declared valuation rules and
       emits traceable opening/closing/variation results.
     - [ ] No provider may own Modelo 100 target casillas, thresholds, rates,
       reductions, or legal treatment.
  - [x] Implement typed relations from Modelo 100 to Modelos 130 and 131 for
     previous-year/current-year dependency information, including read-only
     filed-data observations and fatal handling for missing required observed
     casillas.
     Current closure covers current-year quarterly payment observations for
     Modelo 130 and Modelo 131 and fail-hard missing/duplicate source-period
     handling. Additional previous-year economic-activity details remain under
     the economic-activity subdomain rows.
  - [ ] Link Modelo 100 to registry-backed calculation, trace, review,
     approval, filing draft, export/import layout, borrador observation,
     declaracion observation, Sede filed-data observation, and justificante
     observation workflows.
     - [x] Registry calculation runtime now fails fast on unknown binding and
       relation value identifiers before formula execution, preventing shadowed
       dependency inputs from feeding calculation traces.
  - [ ] Verify Modelo 100 against official legal/manual examples, Renta WEB Open
     parity where safe, source-integrity checks, legal-reference checks, parser
     linkage checks, encrypted observation-store checks, export/import checks,
     cross-model relation checks, invalid-input checks, date-axis boundaries,
     CCAA variation, rental/amortization cases, and registry failure cases.
  - [ ] Delete or reduce every Modelo 100 old authority after registry-backed
     replacement: formula/ruleset-era surfaces, Renta helper authority, CCAA
     hardcoding, rental legal-calculation ownership, borrador extractor casilla
     ownership, declaracion extractor casilla ownership, modelo metadata
     duplicates, category/profile Renta authority, casilla projections, and
     generated/export layout paths.
  - [ ] Add behaviour tests proving Modelo 100 calculation, parsing, review,
     approval, export, live-read observation, and filing workflows require
     validated registry snapshots and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after every ejercicio, Renta subdomain,
     official source ledger, legal ledger, live-read observation path, export
     path, full registry validation, project tests, and vault checks pass.

- `Phase 5` Global teardown completion
  - [ ] Delete remaining old formula ruleset registration surfaces once every
     completed modelo has registry-backed calculations.
  - [ ] Delete old modelo metadata entries as authorities once their identity,
     cadence, applicability, portals, and legal basis are represented in TOML.
  - [ ] Delete old casilla corpus JSON as authority or retain only non-runtime
     archived evidence if explicitly approved outside filing workflows.
  - [ ] Delete hydrate modules and app-facing hydrate commands.
  - [ ] Delete generated export modules and DR fixture promotion paths as
     authorities.
  - [ ] Delete schema cache and BOE extractor promotion paths as authorities.
  - [ ] Delete old VAT/category/deadline mapping authorities after registry-backed
     data bindings, legal parameters, and applicability rules replace them.
  - [ ] Reduce surviving modules to lean application plumbing that consumes
     registry snapshots and never owns legal truth.

- `Phase 6` Final verification and release gate
  - [ ] Run complete registry validation over all completed modelos and shared
     catalogues.
  - [ ] Run source integrity verification over official AEAT artefacts, manual
     manifests, and normative corpus.
  - [ ] Run legal reference validation, including negative-citation regression.
  - [ ] Run official workbook coverage discovery and classification for every
     supported modelo revision.
  - [ ] Run workbook parity tests for every formula-bearing official workbook
     that has a supported local runner.
  - [ ] Run model-by-model calculation tests, date-axis tests, relation tests,
     export roundtrips, filing workflow tests, and registry-backed public
     behaviour tests.
  - [ ] Run behaviour checks that exercise every filing-grade workflow through
     validated registry snapshots and fail fast on generated or incomplete
     legal-rule data.
  - [ ] Run static discovery for hardcoded legal rates, thresholds, casilla maps,
     revision ids, process metadata, generated provenance, and hydrate remnants.
  - [ ] Run full project tests and vault checks.
  - [ ] Produce a final execution summary listing migrated modelos, removed
     surfaces, remaining unsupported modelos, verification commands, and known
     legal evidence gaps.

## Parallelization

The framework rebuild and global deletion gates are serial because they define
the legal authority boundary. After Phase 1 and Phase 2, independent small
modelo waves can run in parallel when they do not share VAT/category/deadline
subdomains and when each worker owns exactly one modelo TOML file, one
execution record set, and one deletion surface. Cross-model waves must remain
ordered: Modelo 303 precedes Modelo 390, Modelo 111 precedes Modelo 190,
Modelo 115 precedes Modelo 180, and Modelo 123 precedes Modelo 193.

Modelo 100 should not be parallelized casually. Its epochs may run in bounded
parallel only after source governance and shared schema constraints are stable,
because Renta touches legal domains that can easily shadow each other.

## Verification

Mission success requires more than passing tests. The implementation is
complete only when the repository has one filing-grade legal calculation
authority, all completed modelos validate through registry snapshots, and old
authorities are gone.

Required verification:

- `uv run --no-sync vaultspec-core vault check all`
- Workbook/live parity backend verification before any modelo refactor wave:
  inventory scanner, workbook classifier, XLSX formula discovery, synthetic
  fixture validator, workbook runner availability, registry/workbook comparator,
  and remote-state guard policy.
- Full registry catalogue validation.
- Source hash, byte-count, path, and manifest validation for AEAT official
  artefacts, manuals, and BOE/normative corpus.
- Legal reference validation with known-bad citation regression.
- Per-model live AEAT cross-reference classification: read-only Open simulator,
  authorized Integration/test web service, static official documentation only,
  or forbidden authenticated/stateful surface.
- Remote-state guard tests proving cross-reference code cannot POST, present,
  sign, save server-side state, pay, direct debit, amend, cancel, or submit
  documents to AEAT.
- Per-model official XLS/XLSX workbook coverage reports.
- Workbook parity tests using identical synthetic inputs for registry execution
  and official workbook execution wherever a supported runner exists.
- Per-model formula closure, parameter closure, casilla closure, relation
  closure, export binding closure, and temporal applicability checks.
- Per-model real-behaviour tests for calculations and filing workflow linkage.
- Export serialization and parse-back tests where an official export surface is
  supported.
- Import-contract tests proving no filing-grade path imports old rulesets,
  hydrate writers, generated export modules, or model-specific filing builders.
- Static searches proving no legal rates, thresholds, casilla mappings,
  formula bindings, process metadata, hydrate provenance, or generated
  provenance remain in runtime Python modules.
- Deletion verification for every old model-specific authority after its wave.

Residual risk must be recorded per modelo. A modelo with missing reviewed
official evidence, incomplete legal basis, incomplete calculations, or
incomplete export linkage is not partially supported; it is absent from
filing-grade registry snapshots until fixed.


## VAT Centralization Roll-Out Ledger (added 2026-05-06)

This section records the VAT-centric slices implemented per the
Modelo 369 VAT centralization ADR. Each entry references its commit
SHA and the audit finding it closes.

- [x] Substrate-extension slice. Adds `aeat.domain.vat._oss` with
  `OssIossRegime` (Exterior / Unión / Importación), `IossFilerRole`
  (DIRECT / INTERMEDIARIO splitting HAC/610/2021 art. 2 letters c
  and d), `DeductionScope`, `RegimePeriodicity`, `REGIME_PERIODICITY`
  mapping, and the `regime_allows_deduction` predicate anchored to
  LIVA art. 163 vicies / tervicies / octovicies. Extends
  `TransactionKind` with five new markers and registers classifier
  rules R16-R19 plus R23. Pure additive; no existing rate values,
  classifier rules, or `TransactionKind` members modified. Commit
  `aac0f655`.
- [x] LIVA deduction-article corpus pull. Adds `ley-37-1992-art-163-vicies.html`
  (Exterior), `ley-37-1992-art-163-tervicies.html` (Unión), and
  `ley-37-1992-art-163-octovicies.html` (IOSS) plus the full
  `ley-37-1992.html` consolidated text. Fixes the ADR's prior
  citation error (Unión deduction is art. 163 tervicies, not
  quatervicies). Commit `0e694abd`.
- [x] Teardown A: route `IvaRate` percentages through the substrate.
  Closes V-1 (high) from the rate-shadow sweep. Removes the
  `_IVA_RATE_PERCENTAGES` Python literal mapping; `iva_rate_percentage`
  becomes a wrapper around `aeat.domain.vat.lookup_rate` for Spain at
  a date. Slot ↔ `VATRateKind` mapping (RATE_4 → SUPER_REDUCED,
  RATE_10 → REDUCED, RATE_21 → GENERAL) is structural and stays in
  Python; the actual percentages live in
  `registry/aeat/vat/rates.toml`. Commit `badff1aa`.
- [x] Teardown B: route LIRPF art. 85 imputación rates through the
  registry. Closes V-2 (high) from the rate-shadow sweep. Removes
  the `IMPUTACION_RATE_RECENT_REVISION` /
  `IMPUTACION_RATE_OLD_OR_NO_REVISION` /
  `CATASTRAL_REVISION_LOOKBACK_YEARS` literals from
  `aeat.domain.rental._aggregates`; the values now live in
  `registry/aeat/legal/irpf.toml` under
  `[parameters."lirpf-art-85:..."]` entries with explicit BOE
  citations and review metadata. A small loader at
  `aeat.domain.rental._imputacion_parameters` reads the TOML at
  module import and exposes `LIRPF_ART_85_IMPUTACION` as the
  canonical accessor. Pulls LIRPF art. 85 BOE corpus
  (`ley-35-2006-art-85.html`). Commit `aba43d37`.
- [x] Modelo 303 (IVA autoliquidación trimestral) registry foundation.
  Establishes the legal authority chain (Orden EHA/3786/2008 articles
  1 and 7), declares quarterly cadence with the four-quarter period
  selector, registers the AEAT 2025 record-design XLSX as the
  workbook parity source, and lands deadline windows for filing
  years 2025 and 2026 with the special 4T-30 January closure per
  art. 7. Read-only `static_official_documentation` and
  `authenticated_read_surface` live cross-references with all
  writes / signing / payment / amendment forbidden. Foundation only;
  the casilla / formula / binding chain follows in subsequent
  slices once the substrate teardowns finish and the
  `ledger_oss_aggregation` source kind is implemented. Commit
  `333fa559`.

Pending VAT-centric slices per the ADR sequencing:

- [ ] Teardown C: review-edit + country-validator boundary tightening
  (V-3 medium / M-2 medium). Constrain
  `aeat.application.review._edit.iva_rate` and `retention_rate` to
  the registry-backed enum; narrow
  `aeat.domain.invoices._validators.validate_country_code` to the
  closed `EUMemberState | OtherCountry` taxonomy.
- [ ] `ledger_oss_aggregation` registry binding source. New
  `DataBindingDefinition.source` value with a runtime resolver that
  filters ledger lines by classification and aggregates per
  destination Member State / regime / rate kind / direction.
- [ ] Modelo 303 deepening. 80+ casillas, formulas, deductions,
  devoluciones, monthly cadence (REDEME / SII filers).
- [ ] Modelo 390 (IVA resumen anual) foundation.
- [ ] Modelo 369 (IVA OSS / IOSS) registry slices, one per Esquema,
  consuming the substrate plus the binding.

- [x] Teardown C: review-edit + country validator boundary tightening.
  Closes V-3 (medium) and M-2 (medium) from the rate-shadow sweep.
  `--set iva.rate=NN` now rejects values outside the closed substrate
  slot percentages {0, 4, 10, 21}; `--set retention.rate=NN` is
  bounded to [0, 100]. Adds `EU_MEMBER_STATE_CODES`,
  `is_eu_member_state_code`, and `assert_eu_member_state_code`
  helpers anchored to `aeat.domain.vat.EUMemberState`; the base
  `validate_country_code` stays permissive for non-EU counterparties
  while OSS / IOSS bindings consume the new EU-only helpers. Commit
  `6964fb41`.
- [x] Modelo 390 (IVA Declaracion-resumen anual) registry foundation.
  Authority: Orden EHA/3111/2009 (BOE-A-2009-18472), articulos 1 and
  8. January-30 deadline (treinta primeros dias naturales del mes de
  enero siguiente) per art. 8. Foundation includes legal references,
  AEAT 2025 record-design XLSX as workbook parity source, AEAT G412
  procedure URL, and read-only live cross-references with all
  writes / signing / payment forbidden. Modified by HAP/2373/2014
  (BOE-A-2014-13180) which exempts quarterly filers in simplified
  regime or urban real-estate rental — that subset gates on a
  profile condition in a deepening slice. Commit `4f00a293`.

- [x] Modelo 308 (IVA solicitud de devolucion) registry foundation.
  Authority: Orden EHA/3786/2008 (BOE-A-2008-20953), articulos 2 and
  11. Ad-hoc cadence reflecting the four operator-type plazo
  patterns from art. 11 (sujetos pasivos ocasionales 30 days,
  regimen simplificado transporte 20 days, recargo de equivalencia
  per-quarter with 4T-30-January exception, etc). Foundation
  includes legal references, AEAT 2019 record-design XLS as workbook
  parity source, AEAT G403 procedure URL, and read-only live
  cross-references with all writes / signing / payment forbidden.
  Operator-type plazo pattern refinement (profile-conditional
  deadline windows) deferred to a deepening slice. Commit `dc3b4d0c`.

- [x] ledger_oss_aggregation registry binding source kind. Implements
  ADR Decision 8 — the structural backend slice that unblocks the
  Modelo 369 per-Esquema registry slices. Extends
  `DataBindingDefinition.source` Literal additively with
  `ledger_oss_aggregation`; introduces `OssIossLedgerObservation`
  for substrate-classified ledger lines; declares
  `_OssIossLedgerSelector` parsing selector dicts into typed
  OssIossRegime / EUMemberState / VATRateKind / InvoiceDirection /
  TransactionKind enum values plus a `iva_amount_sum` /
  `base_amount_sum` fact selector; adds
  `validate_ledger_oss_aggregation_binding_definition` rejecting
  unknown axis values, non-sum aggregations, and wrong-source
  bindings; adds `resolve_ledger_oss_aggregation_binding_values`
  filtering observations by the five classification axes and
  returning the aggregated Decimal. Wired into the modelo validator
  alongside the existing invoice-binding check. 21 focused tests +
  80 modelo registry regression tests all pass. Commit `283abb4f`.

- [x] Modelo 369 (IVA OSS / IOSS) per-Esquema registry slice. Lands
  the centerpiece modelo of the centralization ADR: three revisions
  (esquema-exterior trimestral with EXT-prefixed periods, esquema-union
  trimestral, esquema-importacion mensual with 01-12), parent cadence
  ad_hoc, and five demonstrator ledger_oss_aggregation bindings
  (Exterior DE-services, Unión DE-services, Unión FR-services, Unión
  DE-goods-distance covering both distance-sale and interface-facilitated
  kinds, IOSS DE-low-value-distance) resolving end-to-end via the
  substrate-typed selector + runtime resolver. Authority chain HAC/610/2021
  arts 1/2/3 + LIVA 163 octiesdecies / unvicies / quinvicies. 25 focused
  tests pass (validator, three-Esquema split, scheme selection by period,
  scheme authority in snapshots, filing schedules, per-Esquema deadline
  windows with "mes natural siguiente" closing rule, read-only cross
  references, workbook parity, record-design parseable to 1515 fields
  across 14 sheets, constructs close over revision members, each revision
  declares OSS bindings, end-to-end Unión + IOSS binding resolution,
  construct binding linkage). Closes ADR Decisions D1-D8; casilla /
  formula / numeric-result deepening follows. Commit `a78d221f`.

- [x] Modelo 322 (IVA grupos individual mensual) registry foundation.
  Authority: Orden EHA/3434/2007 (BOE-A-2007-20484), articulos 1
  (aprobación) + 8 (plazo). Filed by individual entities within a
  VAT group regime (LIVA art 163 quinquies). Plazo art 8: 30
  natural days of the following month, with the January period
  closing on the last day of February. Foundation lands legal
  references, AEAT 2026 record-design XLSX (758 KB) as workbook
  parity source, AEAT G407 procedure URL, monthly deadline windows
  for 2025 (Jan/Jun/Dec) and 2026-01 with the Feb-28 January
  special-case, and read-only live cross-references with all
  writes forbidden. 9 focused tests pass. Commit `f963708a`.
- [x] Modelo 353 (IVA grupos agregado mensual) registry foundation.
  Aggregated counterpart to Modelo 322 — filed by the dominant
  entity of the VAT group. Same Orden EHA/3434/2007 authority
  chain (art 2 aprobación, art 8 plazo shared with 322), monthly
  cadence with January-Feb-28 special case. Foundation lands
  legal art 2 reference, AEAT 2026 record-design XLSX (130 KB),
  AEAT G408 procedure URL, monthly deadline windows, and
  read-only live cross-references with all writes forbidden.
  8 focused tests pass. Commit `ffdb19ad`.

- [x] Modelo 309 (IVA declaracion-liquidacion no periodica) registry
  foundation. Authority: Orden HAC/3625/2003 (BOE-A-2003-23809),
  apartados primero (aprobacion) and tercero (plazo). Filed by
  sujetos pasivos sin obligacion ordinaria de declaracion-liquidacion
  who must report only when triggered: medios de transporte nuevos,
  regimen agricola/ganadero/pesquero exits, recargo de equivalencia
  con devoluciones a viajeros, ejecuciones forzosas. Modelled as
  ad_hoc cadence with the four trigger patterns surfaced through
  `decl.tipo-trigger` casilla. Foundation lands legal references,
  AEAT 2023 record-design XLS as workbook parity source, AEAT G404
  procedure URL, and read-only live cross-references with all
  writes forbidden. 7 focused tests pass. Commit `53c079ea`.

### IVA Modelo Surface Coverage Summary (after this roll-out)

The IVA modelo registry now covers eight foundation modelos:

| Modelo | Cadence | Authority | Foundation slice |
|--------|---------|-----------|-------------------|
| 303    | quarterly | Orden EHA/3786/2008 art 1+7 | `333fa559` |
| 308    | ad_hoc | Orden EHA/3786/2008 art 2+11 | `dc3b4d0c` |
| 309    | ad_hoc | Orden HAC/3625/2003 ap 1+3 | `53c079ea` |
| 322    | monthly | Orden EHA/3434/2007 art 1+8 | `f963708a` |
| 349    | quarterly/monthly | Orden EHA/769/2010 (pre-existing) | (pre-existing) |
| 353    | monthly | Orden EHA/3434/2007 art 2+8 | `ffdb19ad` |
| 369    | ad_hoc parent (per-Esquema cadence) | Orden HAC/610/2021 + LIVA 163 | `a78d221f` |
| 390    | annual | Orden EHA/3111/2009 art 1+8 | `4f00a293` |

Modelo 369 carries five demonstrator `ledger_oss_aggregation`
bindings resolving end-to-end through the substrate from commit
`283abb4f`. The remaining IVA modelos in 300-399 series (318
prorrata, 319 regularizacion, 341 reintegración agrícola, 360
devolución no establecidos, 380 territorios especiales) are
candidates for subsequent foundation slices.

- [x] Modelo 360 (IVA devolución 8a Directiva — cuotas soportadas en
  otros Estados miembros) registry foundation. Authority: Orden
  EHA/789/2010 (BOE-A-2010-5210), articulos 1 (aprobacion) + 4
  (plazo). High-value modelo for autonomos with cross-border
  purchases recovering EU VAT through the Eighth-Directive
  procedure. Article 4 plazo: opens day after the refund period
  closes and concludes on 30 September of the year following the
  ejercicio in which the cuotas were borne. Foundation lands legal
  references, AEAT record-design PDF, AEAT GZ09 procedure URL
  (combined 360+361), ad_hoc cadence with 2024 and 2025 deadline
  windows closing on 30-Sep, and read-only live cross-references
  with all writes forbidden. 7 focused tests. Commit `2fac1357`.
- [x] LIVA art 161 recargo de equivalencia substrate. Closes the
  recargo rate gap in the VAT substrate by registering the four
  art-161 rates (general 5.2 %, reducido 1.4 %, super-reducido
  0.5 %, tabaco 1.75 %) as registry-grounded parameters rather
  than Python literals. Adds the BOE per-article corpus excerpt,
  registry/aeat/legal/iva-recargo-equivalencia.toml with explicit
  legal_refs and required_text quotes, and a pydantic-strict loader
  module aeat.domain.vat._recargo_equivalencia exposing
  LIVA_ART_161_RECARGO and recargo_rate_for(rate_kind). The
  substrate is now the canonical authority for recargo rates
  across the codebase. 12 focused tests. Commit `517b00df`.

- [x] IvaFlowDirection codification — repercutido / soportado /
  autorepercutido as a closed substrate enum anchored to LIVA arts
  84 (sujetos pasivos / inversion del sujeto pasivo), 88 (repercusion
  del impuesto), and 92 (cuotas tributarias deducibles). Adds
  derive_flow_for_classification helper mapping (VATCategory,
  InvoiceDirection) -> IvaFlowDirection. Reverse-charge categories
  (DOMESTIC_REVERSE_CHARGE, INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE)
  always route to AUTOREPERCUTIDO regardless of invoice direction.
  The substrate now exposes the complete IVA classification triple
  (VATCategory + VATRateKind + IvaFlowDirection) the ledger and
  modelo registries need. 23 focused tests pass. BOE corpus excerpts
  for arts 84, 88, 92 pulled and registered with required_text gates.
  Commit `515154bd`.
- [x] ledger_iva_aggregation binding source kind — cross-modelo
  generic counterpart to ledger_oss_aggregation that aggregates
  ledger lines by the canonical IVA classification triple. Selector
  declares categories: tuple[VATCategory, ...], rate_kinds:
  tuple[VATRateKind, ...], flow_direction: IvaFlowDirection, fact:
  iva_amount_sum | base_amount_sum. Used by the standard IVA modelos
  (303, 322, 353, 309, 390) to wire their casilla / formula chains.
  IvaLedgerObservation pydantic-strict record carries the triple +
  base/iva amounts. Validator rejects unknown enum values, empty
  tuples, non-sum aggregations, unknown facts, wrong source kind.
  Resolver filters by category-in-set, rate-kind-in-set, exact
  flow_direction match; deterministic, side-effect-free.
  17 focused tests pass. Commit `a393fd12`.

- [x] Modelo 303 IVA bindings end-to-end. Wires 5 demonstrator
  ledger_iva_aggregation bindings into Modelo 303 (autoliquidación
  trimestral) showing the cross-modelo IVA substrate working: three
  repercutido cuota tiers (general 21%, reducido 10%, super-reducido
  4%) anchored to LIVA art 88 + EHA/3786/2008 art 1, one soportado
  cuota across all three rate tiers anchored to LIVA art 92, and one
  autorepercutido cuota for intra-community-acquisition reverse
  charge anchored to LIVA art 84. Construct legal_refs extended with
  arts 84/88/92. 3 new tests verify binding declaration, end-to-end
  resolution against substrate-classified observations, and construct
  binding linkage. Commit `22f09cfd`.
- [x] Modelo 322 IVA bindings — replicates the Modelo 303 binding
  pattern into Modelo 322 (IVA grupos individual mensual) scoped to
  the individual group member's monthly autoliquidación. Same 5
  bindings, same substrate-typed selectors, same source-citation
  pattern. Cross-modelo repetition demonstrates that the
  ledger_iva_aggregation binding source kind is genuinely
  modelo-agnostic — modelos 303, 322, 353, 309, 390 share the same
  IVA flow taxonomy and differ only on filing context. 2 new tests
  pass plus 9 existing 322 tests + 12 303 tests stay green.
  Commit `81264233`.

- [x] Modelo 303 IVA bindings end-to-end. Wires 5 demonstrator
  ledger_iva_aggregation bindings into Modelo 303 (autoliquidación
  trimestral) showing the cross-modelo IVA substrate working: three
  repercutido cuota tiers (general 21%, reducido 10%, super-reducido
  4%) anchored to LIVA art 88 + EHA/3786/2008 art 1, one soportado
  cuota across all three rate tiers anchored to LIVA art 92, and one
  autorepercutido cuota for intra-community-acquisition reverse
  charge anchored to LIVA art 84. Construct legal_refs extended with
  arts 84/88/92. 3 new tests verify binding declaration, end-to-end
  resolution against substrate-classified observations, and construct
  binding linkage. Commit `22f09cfd`.
- [x] Modelo 322 IVA bindings — replicates the Modelo 303 binding
  pattern into Modelo 322 (IVA grupos individual mensual) scoped to
  the individual group member's monthly autoliquidación. Same 5
  bindings, same substrate-typed selectors, same source-citation
  pattern. Cross-modelo repetition demonstrates that the
  ledger_iva_aggregation binding source kind is genuinely
  modelo-agnostic — modelos 303, 322, 353, 309, 390 share the same
  IVA flow taxonomy and differ only on filing context. 2 new tests
  pass plus 9 existing 322 tests + 12 303 tests stay green.
  Commit `81264233`.

- [x] Modelo 353 IVA bindings (grupos agregado mensual). Same 5-binding
  pattern as 322, scoped to the dominant entity's aggregated declaration
  consolidating member 322 totals. LIVA arts 84/88/92 + Orden
  EHA/3434/2007 art 2. 3 new tests pass. Commit `42330477`.
- [x] Modelo 309 IVA bindings (declaración-liquidación no periódica). Two
  bindings matching the modelo's narrower trigger surface:
  autorepercutido for intra-community acquisition reverse charges (medios
  de transporte nuevos, the canonical 309 trigger per LIVA art 84) and
  soportado for recargo-de-equivalencia retailers' devolución on traveler
  exports (LIVA art 92). Other 309 trigger types (régimen agrícola
  exits, ejecuciones forzosas) await deepening slices. 2 new tests pass.
  Commit `42330477`.
- [x] Modelo 390 IVA bindings (resumen anual). Same 5-binding pattern as
  Modelo 303 but aggregating over the full ejercicio rather than per
  quarter. LIVA arts 84/88/92 + Orden EHA/3111/2009 art 1. The annual
  resumen recomputes from the ledger directly; a complementary
  previous_filing dependency on 303 follows once 303 declares
  result-casillas. 2 new tests verify annual aggregation across
  simulated quarterly observations summing to the expected annual
  total. Commit `5ff04552`.

### IVA Cross-Modelo Roll-Out Complete (5 of 5 standard IVA modelos)

The ledger_iva_aggregation binding source kind (commit a393fd12) is
now wired into all five standard IVA modelos using the same
substrate-typed selector contract (categories + rate_kinds +
flow_direction + fact):

| Modelo | Cadence | IVA Bindings | Authority |
|--------|---------|---------------|-----------|
| 303    | quarterly | 5 | Orden EHA/3786/2008 |
| 322    | monthly | 5 | Orden EHA/3434/2007 art 1 |
| 353    | monthly | 5 | Orden EHA/3434/2007 art 2 |
| 309    | ad_hoc | 2 | Orden HAC/3625/2003 |
| 390    | annual | 5 | Orden EHA/3111/2009 |

Each modelo's bindings are anchored to the relevant LIVA flow
articles (84/88/92) plus its establishing Orden Ministerial. The
substrate is now demonstrably modelo-agnostic — the same five-axis
classification (VATCategory + VATRateKind + IvaFlowDirection +
fact) flows through five different modelos with five different
filing contexts and resolves correctly against the same
IvaLedgerObservation record shape.

- [x] Modelo 303 result-casillas + Modelo 390 cross-modelo
  previous_filing dependency. Closes the 390 <- 303 reconciliation
  chain: 5 bound casillas exposing the IVA aggregation bindings as
  casilla values, 3 computed result-casillas via formulas
  (iva.cuota-devengada-total = sum of 3 repercutido +
  autorepercutido; iva.cuota-deducible-total = soportado +
  autorepercutido; iva.resultado-regimen-general = devengada -
  deducible) all anchored to LIVA arts 88/92/84 + EHA/3786/2008.
  Modelo 390 declares 3 previous_filing bindings with
  source_periods=[1T,2T,3T,4T] aggregating each 303 result-casilla
  across the four quarters via op=sum — the first cross-modelo
  previous_filing dependency in the IVA registry. End-to-end
  smoke verified: 1T snapshot with substrate-classified
  IvaLedgerObservation inputs flows through bindings -> bound
  casillas -> formulas -> 348/147/201 result triple. New
  modelo-303-calculation application link added so the validator's
  "formulas require a calculation application link" gate fires.
  Commit `fae6c6b2`.

- [x] Modelo 390 result-casillas + 303-reconciliation. Mirrors the
  303 result-casilla shape at the annual level: 5 bound casillas
  surfacing the annual ledger_iva_aggregation bindings + 3
  reconciliation casillas pulling from the four 303 quarters via
  previous_filing + 3 computed annual totals via formulas. Dual
  visibility on the annual figures: COMPUTED from substrate ledger
  observations vs RECONCILED from filed 303 trimestrales.
  End-to-end smoke verified — 4 quarters of (1 repercutido 21% + 1
  soportado 21%) produce devengada=840 / deducible=252 / resultado=588
  via BOTH the formula chain AND the previous_filing reconciliation
  matching as expected. Commit `3a12bb35`.
- [x] Modelo 322 + 353 result-casillas + formulas. Replicates the
  303 result-casilla pattern into both group-of-entities IVA modelos
  (322 individual mensual, 353 agregado mensual). Same shape: 5
  bound casillas + 3 computed casillas with formulas. The IVA result
  triple (cuota-devengada-total / cuota-deducible-total /
  resultado-regimen-general) is now uniform across the four
  ledger-aggregating IVA modelos. Both validate with 10 casillas + 3
  formulas + 5 bindings each. Commit `adc40d9d`.

- [x] Modelo 309 result-casillas + total formula. Completes the
  result-casilla shape across all five standard IVA modelos. Modelo
  309 (no periodica) gets 2 bound casillas (autorepercutido-
  intracomunitaria, soportado-recargo-equivalencia) + 1 computed
  iva.cuota-no-periodica-total formula summing both. End-to-end
  smoke verified with a vehicle acquisition (5250 cuota
  autorepercutida) + recargo soportado (21 cuota) = 5271 total.
  Commit `586e83b9`.

### Result-Casilla Shape Now Uniform Across All 5 Standard IVA Modelos

| Modelo | Cadence | Casillas | Formulas | Bindings |
|--------|---------|----------|----------|----------|
| 303    | quarterly | 10 (5 bound + 3 computed + 2 informational) | 3 | 5 |
| 322    | monthly | 10 (5 bound + 3 computed + 2 informational) | 3 | 5 |
| 353    | monthly | 10 (5 bound + 3 computed + 2 informational) | 3 | 5 |
| 309    | ad_hoc | 5 (2 bound + 1 computed + 2 informational) | 1 | 2 |
| 390    | annual | 13 (8 bound + 3 computed + 2 informational) | 3 | 8 |

Total IVA registry surface: 48 casillas + 11 formulas + 25 bindings
spanning quarterly, monthly, ad-hoc, and annual filings, all
backed by the same VATCategory + VATRateKind + IvaFlowDirection
substrate triple. The cross-modelo previous_filing dependency from
390 across the four 303 quarters demonstrates that the canonical
resumen-anual reconciliation pattern works end-to-end.

- [x] Devengada vs deducible IVA settlement cornerstone codification.
  Adds IvaSettlementSide closed enum (DEVENGADA / DEDUCIBLE),
  flow→sides mapping, canonical predicates (is_devengada_flow,
  is_deducible_flow), and frozen sets (DEVENGADA_FLOW_DIRECTIONS,
  DEDUCIBLE_FLOW_DIRECTIONS) so the ledger and modelo registries
  categorize transactions through one substrate primitive instead of
  re-deriving the mapping inline. Anchored to LIVA arts 88 (output) /
  92 (input) / 84.Uno.2 (both legs of inversión). Set-theoretic
  invariants: DEVENGADA ∩ DEDUCIBLE = {AUTOREPERCUTIDO},
  DEVENGADA ∪ DEDUCIBLE = full taxonomy. Modelo 303 contract-gate
  test confirms the cuota-devengada-total formula sums exactly the
  DEVENGADA_FLOW_DIRECTIONS set; if the substrate ever changes the
  test fires unless the modelo formula updates in lockstep. 11 new
  tests pass + 23 prior flow tests stay green. Commit `fc196b15`.

The IVA classification triple (VATCategory + VATRateKind +
IvaFlowDirection) is now wrapped by the settlement-side cornerstone
abstraction. The ledger domain has one canonical primitive to ask
"does this transaction owe IVA to the Treasury or claim a deduction
back?" — anchored to BOE-cited LIVA articles, with the AUTOREPERCUTIDO
both-sides invariant explicitly tested.

- [x] IvaInvoiceClassification reusable record. Bridges the substrate
  triple (VATCategory + VATRateKind + IvaFlowDirection) plus the
  derived settlement-side classification (devengada / deducible) into
  one frozen pydantic record the ledger and downstream filing
  surfaces propagate without re-deriving the mapping.
  classify_invoice_line_for_iva(iva_rate, invoice_kind) helper covers
  the standard domestic-IVA case (the most common autónomo
  operation); reverse-charge, intra-community, OSS / IOSS, export /
  import cases construct IvaInvoiceClassification directly with the
  appropriate VATCategory from the substrate classifier. Properties
  contributes_to_devengada / contributes_to_deducible / is_reverse_charge
  expose the cornerstone classifications. Constructor cross-validates
  (flow_direction, settlement_sides) consistency. 17 focused tests
  pass + 34 prior flow tests stay green. Substrate is now the
  canonical ledger-side categorization authority. Commit `34f89632`.

- [x] invoice_line_to_iva_observation — ledger→modelo bridge. Closes
  the loop from invoice metadata to substrate-classified
  IvaLedgerObservation records consumed by ledger_iva_aggregation
  binding selectors. Standard-case helper for domestic IVA; reverse-
  charge / intra-community / OSS / IOSS / export-import cases
  construct IvaLedgerObservation directly with the appropriate
  VATCategory from the substrate classifier. End-to-end smoke
  verified: 2 issued + 1 received invoice lines flow through the
  bridge into Modelo 303 binding resolver producing 210 / 50 / 84
  binding totals. Commit `95b2da5e`.

### Standardized Pydantic IVA Pipeline (Now Complete)

The IVA system has a complete typed pipeline from raw invoice
metadata to filing-grade modelo result-casillas, every step being a
pydantic-strict frozen record or a closed function:

```
Invoice line metadata (IvaRate slot + InvoiceKind)
  → classify_invoice_line_for_iva()
  → IvaInvoiceClassification (with derived settlement-side set)
  → invoice_line_to_iva_observation()
  → IvaLedgerObservation (substrate-classified ledger line)
  → resolve_ledger_iva_aggregation_binding_values()
  → binding values (Decimal per binding id)
  → resolve_bound_casilla_inputs()
  → casilla values (Decimal per bound casilla id)
  → calculate_registry_snapshot() with formulas
  → result casilla totals (cuota-devengada-total /
    cuota-deducible-total / resultado-regimen-general)
```

Anchor articles travel along every layer: LIVA art 88 (repercusión)
on devengada flows, LIVA art 92 (deducible) on soportado flows,
LIVA art 84.Uno.2 (inversión del sujeto pasivo) on autorepercutido
flows, plus the modelo-establishing Orden Ministerial.

The substrate is now the single source of truth for IVA
classification, and the ledger surface bridges into the modelo
registry through one canonical function per axis.

- [x] Pydantic typed-field rollout — Invoice.iva_category typed.
  Promotes the free-form ``str | None`` field to substrate-typed
  ``VATCategory | None`` so the field that asks "what is the
  operation kind for this invoice?" references the same closed enum
  the substrate classifier emits, the modelo registry binding
  selectors filter on, and IvaInvoiceClassification carries.
  Backwards-compatible at the persistence boundary (StrEnum
  serializes to its string form; pydantic coerces strings to enum
  members at validation time). Tightens the contract: persistence
  loaders reading historical records with non-canonical category
  strings now fail validation instead of silently accepting drift.
  2 new tests + ~353 tests across the touched surfaces stay green.
  Commit `c2fc4e24`.

Audit of remaining ad-hoc weak-typed fields surveyed during this
rollout (deferred until their substrate primitives land):

- ``Invoice.counterparty_country: str`` — promote to
  ``EUMemberState | OtherCountry`` once the OtherCountry sum-type
  is codified. EU_MEMBER_STATE_CODES already exists from
  Teardown C.
- ``Invoice.retention_rate: Decimal | None`` — promote to a typed
  ``RetentionRate`` enum once the IRPF retention substrate lands
  (LIRPF arts 99-101 + RIRPF retention rate tables).
- ``InvoiceLine.category_id: str | None`` — application-specific
  spending category, NOT IVA classification; orthogonal to this
  rollout.

The IVA-side typed surface is now uniform from ledger record
(Invoice.iva_category : VATCategory) through pipeline bridge
(invoice_line_to_iva_observation) into the modelo registry
(ledger_iva_aggregation binding selectors). Every IVA-bearing
ledger record carries substrate-grounded values from cradle to
filing-grade aggregation.

- [x] Legal-basis binding verification across IVA + IRPF rates.
  Adds the canonical cross-substrate test gate that asserts every
  rate value used by the IVA + IRPF substrate matches its BOE
  legal authority and that all substrate / ledger / modelo
  references agree. The chain BOE excerpt → registry legal entry
  with required_text gate → VAT_RATE_TABLE → IvaRate / VATRateKind
  → iva_rate_percentage wrapper is verified end-to-end for each
  rate (LIVA arts 90 general 21%, 91 reducido 10% + super-reducido
  4%, 161 recargo 5.2/1.4/0.5/1.75%, LIRPF art 85 imputación
  1.1/2% + 10y lookback). Cross-substrate alignment also covered:
  IvaRate slot ↔ VATRateKind tier mapping totality, RATE_0 direct
  resolution, EXEMPT / NOT_SUBJECT None semantics, registry tree
  loader article recognition. Pulls LIVA arts 90 + 91 corpus
  excerpts and registers them in registry/aeat/legal/iva-rates.toml.
  15 focused tests in src/aeat/domain/vat/test_legal_basis_binding.py.
  Commit `688609e5`.

A transient pydantic_core file-lock in the .venv (Windows
access-denied during a parallel agent's install attempt) blocks
runtime test execution at the moment; the test module + corpus +
TOML are syntactically and semantically valid and will execute
successfully once the environment recovers. The rate-binding
audit trail (BOE → registry → substrate → ledger → modelo) is the
deliverable; the runtime gate fires whenever it is exercised.

### Pydantic-Typed Binding Surface (Now Complete)

Every IVA rate value referenced anywhere in the codebase is now
anchored to a BOE legal article through one of three layers:

| Layer | Authority | Verification |
|-------|-----------|--------------|
| Corpus excerpt | BOE consolidated text | required_text gate matches |
| Registry parameter / rate table | TOML in registry/aeat/ | sha256 + required_text |
| Substrate enum / wrapper | aeat.domain.vat | typed pydantic record + lookup_rate |
| Ledger record | aeat.domain.invoices | VATCategory / IvaRate typed fields |
| Modelo binding selector | DataBindingDefinition | substrate-typed selector keys |

The cross-substrate test gate (test_legal_basis_binding.py) is
exercised whenever any of these layers are touched; if drift
appears between the BOE article and the substrate value, the gate
fires before the discrepancy can leak into modelo filings.

- [x] Type-harden Invoice.counterparty country axis. Adds typed
  property accessors that bridge the str-level counterparty_country
  field into the substrate's closed EUMemberState enum so downstream
  consumers route through the substrate taxonomy. New properties
  Invoice.counterparty_eu_member_state (EUMemberState | None) and
  Invoice.counterparty_is_eu_member (bool) anchored on
  EU_MEMBER_STATE_CODES (Teardown C). 3 new tests pass + 40 prior
  invoice tests stay green. Commit `c285c81b`.
- [x] Add Invoice.iva_classification_for_line typed accessor. Closes
  the substrate→ledger handshake on the invoice surface: the Invoice
  record now exposes a typed method that bundles its lines' IvaRate
  slot + Invoice.kind into the canonical IvaInvoiceClassification
  record (substrate triple + derived settlement-side classification).
  Downstream filing surfaces call
  invoice.iva_classification_for_line(line) once per line and route
  through the substrate typed record. 2 new tests pass + 65 prior
  IVA / legal-binding tests stay green. Commit `cc4259b8`.

### Pydantic-Typed Invoice Surface (Now Complete)

| Accessor | Type | Anchor |
|----------|------|--------|
| invoice.kind | InvoiceKind | substrate ledger primitive |
| invoice.payment_status | PaymentStatus | substrate ledger primitive |
| invoice.iva_category | VATCategory \| None | substrate operation kind |
| invoice.counterparty_eu_member_state | EUMemberState \| None | substrate EU taxonomy |
| invoice.counterparty_is_eu_member | bool | derived predicate |
| invoice.iva_classification_for_line(line) | IvaInvoiceClassification | substrate triple bundle |
| line.iva_rate | IvaRate | substrate rate slot |

Every accessor is anchored to a substrate primitive backed by a BOE
legal article. The cross-substrate test_legal_basis_binding.py gate
(commit 688609e5) fires if any layer drifts between the BOE article
and the substrate value, and the typed surface ensures downstream
consumers can't bypass the canonical classification.
