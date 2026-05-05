---
tags:
  - '#plan'
  - '#calculation-truth-registry'
date: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-inventory-research]]'
  - '[[2026-05-03-external-tax-definition-engines-reference]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-research]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-research]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
- [ ] Modelo 111 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 111 filing-grade values.

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
- [x] Modelo 115 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
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
- [x] Modelo 123 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
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
- [ ] Modelo 123 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 123 filing-grade values.

### Wave 5 Modelo 131 Parity Ledger

- [ ] Modelo 131 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 131 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 131 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
  - [x] Modelo 131 current 2026 legal basis: catalogue RD 439/2007 article 110
    and Orden EHA/672/2007 article 1 for the current objective-estimation
    payment foundation.
  - [x] Modelo 131 annual module-order basis: catalogue BOE module orders for
    2024, 2025, and 2026 so year-scoped objective-estimation revisions can cite
    their applicable signs, indices, modules, and instructions.
- [x] Modelo 131 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [x] Modelo 131 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [x] Modelo 131 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 131 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 131 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
  - [x] Modelo 131 current 2026 catalogue closure: add current instructions,
    procedure, BOE form authority, and 2026 record-design source references
    with corpus paths and integrity data.
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
- [ ] Modelo 131 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
  - [x] Modelo 131 current 2026 liquidacion casillas: define casillas 01
    through 15 with manual/computed classification, sections, legal refs, and
    source refs.
- [ ] Modelo 131 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
  - [x] Modelo 131 current 2026 liquidacion formulas: define 2 percent payment
    rates and computed casillas 04, 06, 07, 10, 13, and 15 through the registry
    runtime.
- [ ] Modelo 131 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
  - [x] Modelo 131 current 2026 declaration-copy profile: define strict
    declaration-PDF extraction coverage for casillas 01 through 15.
- [ ] Modelo 131 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
  - [x] Modelo 131 current 2026 static surface decision: register the official
    static documentation cross-reference and forbidden AEAT write actions.
- [ ] Modelo 131 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
  - [x] Modelo 131 current 2026 application links: register calculation,
    filing, verification, review, extraction, portal, and deadline consumers
    against validated snapshots.
  - [ ] Modelo 131 export layout support: extend or model the official
    activity-detail record structures before adding export roundtrips.
- [ ] Modelo 131 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, and any filed-data
  bindings are correct against official authority.
  - [x] Modelo 131 current 2026 behaviour tests: calculate objective-estimation
    totals through the committed registry and verify deadline applicability
    through the registry-backed deadline engine.
- [ ] Modelo 131 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 131 teardown: delete or neutralize all old Modelo 131 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 131 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
  - [x] Modelo 131 current 2026 focused gate: run registry verification,
    calculation/deadline/setup tests, `ruff`, `ty`, `git diff --check`, and
    development-metadata sanitization scans for the touched surfaces.
- [ ] Modelo 131 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 131 filing-grade values.

### Wave 6 Modelo 180 Parity Ledger

- [ ] Modelo 180 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 180 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
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
- [ ] Modelo 180 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 180 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [x] Modelo 180 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 180 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 180 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  115, and any filed-data bindings are correct against official authority.
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
- [ ] Modelo 190 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 190 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 190 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 190 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 190 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 190 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  111, and any filed-data bindings are correct against official authority.
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
- [ ] Modelo 193 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 193 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 193 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 193 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 193 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 193 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  123, and any filed-data bindings are correct against official authority.
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

- [ ] Modelo 347 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 347 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 347 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 347 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 347 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 347 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 347 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 347 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 347 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/347.toml`.
- [ ] Modelo 347 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 347 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 347 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 347 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 347 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 347 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, aggregation
  thresholds, and any filed-data bindings are correct against official
  authority.
- [ ] Modelo 347 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 347 teardown: delete or neutralize all old Modelo 347 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 347 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 347 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 347 filing-grade values.

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

- [ ] Modelo 202 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 202 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 202 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 202 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 202 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 202 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 202 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 202 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 202 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/202.toml`.
- [ ] Modelo 202 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 202 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 202 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 202 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 202 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 202 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, corporate instalment
  methods, and any filed-data bindings are correct against official authority.
- [ ] Modelo 202 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 202 teardown: delete or neutralize all old Modelo 202 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 202 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 202 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 202 filing-grade values.

### Wave 15 Modelo 200 Parity Ledger

- [ ] Modelo 200 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 200 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 200 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 200 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 200 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 200 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 200 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 200 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 200 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/200.toml`.
- [ ] Modelo 200 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 200 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 200 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 200 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 200 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 200 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relation to Modelo
  202, and any filed-data bindings are correct against official authority.
- [ ] Modelo 200 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 200 teardown: delete or neutralize all old Modelo 200 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 200 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 200 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 200 filing-grade values.

### Wave 16 Modelo 232 Parity Ledger

- [ ] Modelo 232 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 232 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 232 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 232 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 232 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 232 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 232 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 232 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 232 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/232.toml`.
- [ ] Modelo 232 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 232 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 232 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 232 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 232 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 232 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, reporting
  thresholds, and any filed-data bindings are correct against official
  authority.
- [ ] Modelo 232 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 232 teardown: delete or neutralize all old Modelo 232 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 232 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 232 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 232 filing-grade values.

### Wave 17 Modelo 720 Parity Ledger

- [ ] Modelo 720 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 720 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 720 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 720 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 720 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 720 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 720 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 720 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 720 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/720.toml`.
- [ ] Modelo 720 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 720 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 720 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 720 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 720 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 720 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, asset thresholds,
  and any filed-data bindings are correct against official authority.
- [ ] Modelo 720 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 720 teardown: delete or neutralize all old Modelo 720 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 720 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 720 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 720 filing-grade values.

### Wave 18 Modelo 840 Parity Ledger

- [ ] Modelo 840 audit: enumerate every current code, corpus, TOML, parser,
  fixture, workflow, and test surface that codifies Modelo 840 identity,
  casillas, rules, calculations, deadlines, exports, or live filed data.
- [ ] Modelo 840 legal basis: identify and catalogue BOE legal references for
  every filing-grade calculation, parameter, filing condition, and temporal
  applicability rule.
- [ ] Modelo 840 AEAT official guidance: capture and hash AEAT instructions,
  manuals, record designs, and other official source artefacts required by the
  registry definition.
- [ ] Modelo 840 workbook/layout coverage: discover official XLS/XLSX coverage,
  classify each artefact by evidence tier, and record whether it proves layout
  only or executable calculation parity.
- [ ] Modelo 840 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, and justificante availability.
- [ ] Modelo 840 live sanitized fixture: capture at least one read-only live
  submitted-file or declaration-copy artefact, sanitize identity data, commit
  the redacted fixture, and prove it parses through the registry layout.
- [ ] Modelo 840 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 840 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/840.toml`.
- [ ] Modelo 840 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, and source
  refs.
- [ ] Modelo 840 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, relation, rounding rule, legal ref,
  source ref, and trace output.
- [ ] Modelo 840 extraction profiles: define submitted-file and declaration PDF
  extraction profiles with target casillas, accepted artefacts, min coverage,
  failure semantics, legal refs, and source refs.
- [ ] Modelo 840 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, and cancellation actions.
- [ ] Modelo 840 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 840 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, census/activity
  conditions, and any filed-data bindings are correct against official
  authority.
- [ ] Modelo 840 live/filed-data tests: run committed sanitized submitted-file
  and declaration-copy parser tests, encrypted observation-store roundtrip
  tests where applicable, and filed-data parser tests without defaults or
  silent degradation.
- [ ] Modelo 840 teardown: delete or neutralize all old Modelo 840 authorities
  in rulesets, filing builders, category mappings, casilla projections,
  deadlines, generated exports, hydrate paths, and legacy fixtures.
- [ ] Modelo 840 quality gate: run registry verification, focused public
  workflow tests, source-integrity checks, remote-state checks, `ruff`, `ty`,
  `git diff --check`, and development-metadata sanitization checks.
- [ ] Modelo 840 completion gate: mark complete only when no unchecked row
  remains and no old authority can populate Modelo 840 filing-grade values.

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
- [ ] Modelo 100 live filed-data discovery: list available AEAT filed rows
  through the read-only surface and record the periods, submitted-file
  availability, declaration-copy availability, justificante availability,
  borrador/data-fiscal availability, and forbidden authenticated surfaces.
- [ ] Modelo 100 live sanitized fixture: capture at least one read-only live
  submitted-file, declaration-copy, or official filed-data artefact, sanitize
  identity data, commit the redacted fixture, and prove it parses through the
  registry layout.
- [ ] Modelo 100 legal/source catalogue closure: add every legal ref and source
  ref to `registry/aeat/legal/` with corpus paths, hashes, evidence tier, and
  applicability dates.
- [ ] Modelo 100 TOML identity and revisions: define modelo identity, title,
  jurisdiction, cadence, every supported revision, period selector, deadline
  windows, and application links in `registry/aeat/modelos/100.toml`.
- [ ] Modelo 100 casilla schema: define every filing-grade casilla with data
  type, input kind, requiredness, section, export refs, legal refs, source
  refs, and Renta epoch grouping.
- [ ] Modelo 100 formulas, parameters, and bindings: define every computation,
  dated value, previous-filing binding, cross-model relation, CCAA parameter,
  rental algorithm, rounding rule, legal ref, source ref, and trace output.
- [ ] Modelo 100 extraction profiles: define submitted-file, declaration PDF,
  borrador, and data-fiscal extraction profiles with target casillas, accepted
  artefacts, min coverage, failure semantics, legal refs, and source refs.
- [ ] Modelo 100 live cross-reference guard: record the official live/static
  cross-reference decision and prove remote-state guards reject AEAT writes,
  saves, presentation, signing, payment, amendment, cancellation, and
  authenticated Renta WEB synthetic-test actions.
- [ ] Modelo 100 export/filing linkage: route export, verify, calculation,
  review, approval, reconciliation, and workflow entry points through validated
  registry snapshots.
- [ ] Modelo 100 legal correctness tests: run behaviour tests that prove formula
  outputs, trace legal refs, source refs, date boundaries, relations to Modelos
  130 and 131, Renta epochs, CCAA behaviour, rental behaviour, and any
  filed-data bindings are correct against official authority.
- [ ] Modelo 100 live/filed-data tests: run committed sanitized submitted-file,
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
  - [x] Extend validator failure semantics so a filing-grade formula cannot be
     validated from layout authority alone and cannot use executable parity as
     a substitute for BOE legal basis.
  - [x] Extend formula and parameter source grounding so official-source
     guidance citations must resolve to reviewed source text in the local AEAT
     corpus before a registry snapshot validates.
  - [x] Extend legal grounding so legal catalogue references can require BOE
     corpus text and registry validation fails when the cited local legal text
     does not contain the required legal anchors.
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
  - [ ] Verify Modelo 180 with real annual-summary examples, relation tests over
     Modelo 115 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
  - [ ] Delete Modelo 180 old authorities in rulesets, annual summary code,
     declaration extractor truth, casilla projections, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 180 relation and filing workflows
     require a validated registry snapshot and fail fast on coverage gaps.
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
  - [ ] Link Modelo 190 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
  - [ ] Verify Modelo 190 with real annual-summary examples, relation tests over
     Modelo 111 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
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
  - [ ] Link Modelo 193 to registry-backed relation resolution, trace, review,
     approval, filing draft, declaration parsing where relevant, and export
     workflows.
  - [ ] Verify Modelo 193 with real annual-summary examples, relation tests over
     Modelo 123 outputs, invalid inputs, legal-reference checks,
     source-integrity checks, export roundtrips, and registry failure cases.
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
  - [ ] Verify Modelo 232 with real reporting-condition examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 232 old authorities in declaration extractor truth, modelo
     metadata duplicates, casilla projections, related-party hardcoding, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 232 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
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
  - [ ] Verify Modelo 720 with real asset-class examples, threshold failures,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 720 old authorities in declaration extractor truth, modelo
     metadata duplicates, casilla projections, foreign-asset hardcoding, and
     generated export/layout paths.
  - [ ] Add behaviour tests proving Modelo 720 filing workflows require a
     validated registry snapshot and fail fast on coverage gaps.
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

- `Wave 21` Modelo 100 Renta universe complete implementation
  - [ ] Audit every Modelo 100 authority in rulesets, Renta helper modules,
     anexo modules, CCAA modules, rental modules, amortization modules,
     inventory modules, minimos/tarifa logic, borrador extractors, declaration
     extractors, modelo metadata, casilla corpus, manuals, BOE references,
     XSD/properties dictionaries, export or filing specs, tests, and official
     AEAT source material.
  - [ ] Produce a Modelo 100 model-law coverage ledger covering every supported
     revision, handbook part, BOE legal act, autonomous-community legal source,
     anexo, summary casilla, formula, parameter, algorithm binding, data
     binding, relation to Modelos 130 and 131, source artefact, filing path,
     parser path, test area, and old authority to delete.
  - [ ] Research and verify Renta source governance: official AEAT handbook
     parts, BOE legal basis, XSD/properties dictionaries, declaration
     extraction references, summary casillas, and negative citation controls.
  - [ ] Classify Renta WEB Open for Modelo 100 live cross-reference and add
     remote-state guard tests; authenticated Renta WEB, borrador, fiscal-data,
     signing, presentation, server-side save, and any AEAT write action are
     forbidden for synthetic calculation tests.
  - [ ] Write the Modelo 100 registry scaffold in `registry/aeat/modelos/100.toml`
     with identity, revisions, filing cadence, common legal basis, summary
     casillas, final settlement structure, source references, and legal
     references.
  - [ ] Migrate Modelo 100 income-type formulas and anexo structures into
     reviewed registry definitions with legal references, source references,
     typed formulas, and trace requirements.
  - [ ] Migrate Modelo 100 reductions, minimos, bases, cuotas, tarifa behaviour,
     parameter tables, temporal applicability, and calculation trace coverage.
  - [ ] Migrate Modelo 100 CCAA rules with autonomous-community legal evidence,
     temporal applicability, foral exclusions, Ceuta/Melilla handling, and
     contradiction checks.
  - [ ] Migrate Modelo 100 rental, amortization, inventory, and related ledgers
     into registry-backed algorithm bindings with explicit legal constants,
     input bindings, output casillas, deterministic execution, and trace
     contracts.
  - [ ] Migrate Modelo 100 deductions, anexo-specific behaviours, borrador
     parsing linkage, declaration extraction linkage, and export or filing
     linkage into registry-backed paths.
  - [ ] Link Modelo 100 to registry-backed calculation, trace, review, approval,
     filing draft, borrador parsing where relevant, declaration parsing where
     relevant, and export or submission workflows.
  - [ ] Verify Modelo 100 with real Renta examples across income types, summary
     calculations, CCAA variation, rental/amortization cases, invalid inputs,
     date-axis boundaries, relation tests to Modelos 130 and 131,
     legal-reference checks, source-integrity checks, parser linkage checks,
     filing/export checks, and registry failure cases.
  - [ ] Delete Modelo 100 old authorities in Renta rulesets, Renta helper
     modules, CCAA hardcoding, rental legal-calculation authority, borrador
     extractor casilla truth, declaration extractor casilla truth, modelo
     metadata duplicates, casilla projections, and generated/export layout
     paths.
  - [ ] Add behaviour tests proving Modelo 100 calculation, parsing, review,
     approval, export, and filing workflows require validated registry snapshots
     and fail fast on coverage gaps.
  - [ ] Mark the wave complete only after every Renta epoch, full registry
     validation, project tests, and vault checks pass.

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
