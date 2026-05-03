---
tags:
  - '#plan'
  - '#calculation-truth-registry'
date: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-inventory-research]]'
  - '[[2026-05-03-external-tax-definition-engines-reference]]'
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
rules, schema generation, and export generation are migration sources only.
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
- Existing code may be read as migration evidence, but the old folders and
  modules are deleted or reduced to non-authoritative plumbing by the end of
  their wave.
- Tests must verify real behaviour, legal reference closure, source integrity,
  formula closure, export alignment, and import boundaries.

Each modelo wave is a complete implementation of exactly one modelo. A wave is
not complete until audit, research, discovery, registry data, calculation
runtime linkage, export or filing linkage, legal verification, calculation
verification, deletion of old authorities, and import-contract enforcement are
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
  its model-law coverage ledger. Formula-bearing official AEAT workbooks become
  parity targets; static layouts, unsupported binary XLS files, and unreadable
  artefacts become explicit coverage gaps.
- Synthetic parity input sets are single-source fixtures for each
  modelo/revision. The same inputs must be applied to the registry engine and
  the workbook/simulator parity surface before comparing outputs.
- Every export or programmatic filing path resolves through registry export
  layouts and validated snapshots. A model with no supported export or filing
  linkage is not production-ready.
- Every old model-specific authority is deleted or reduced to non-authoritative
  plumbing. The import-contract tests must prove it cannot be used for
  filing-grade calculation.
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
| 20 | 037 | Simplified censal declaration if reviewed official evidence exists; otherwise explicit removal from filing-grade support. | Censal hydrate tables, declaration extractor truth, any implied support without official evidence. | Classify official live/static surface; retired or unsupported current surfaces fail closed and cannot be demoed as filing-capable. |
| 21 | 100 | Renta universe: source governance, summary, anexos, income types, reductions, minimos, bases, cuotas, CCAA rules, rental, amortization, deductions, borrador/declaration linkage, export or filing linkage. | All Renta rulesets, Renta helper modules, CCAA hardcoding, rental legal-calculation authority, borrador/extractor casilla truth. | Research Renta WEB Open as read-only cross-reference evidence; authenticated Renta WEB/borrador/data-fiscal flows are forbidden for synthetic calculation tests. |

## Tasks

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

- `Phase 0A` Approval, governance, and hard-cut controls
  - [x] Treat the accepted ADR as the controlling architecture for all subsequent
     registry work.
  - [x] Define the wave completion contract: each modelo must have reviewed TOML,
     strict registry validation, legal/source evidence, calculation tests,
     export or filing linkage, trace output, and deletion of old model-specific
     authority.
  - [x] Define the teardown contract: old code may be read for migration and may
     be cited in execution records, but it is not retained as a runtime fallback
     or alternate source of truth.
  - [x] Establish import-boundary rules that forbid filing, review, export, CLI,
     and application code from importing old formula rulesets, hydrate writers,
     generated export modules, or model-specific filing builders as calculation
     authorities.
  - [x] Establish execution-record requirements for every wave: audit notes,
     source/legal evidence notes, migrated formula notes, verification evidence,
     and deletion evidence.

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

- `Phase 2` Repository shape, shared data, and global deletion gates
  - [ ] Create `registry/aeat/legal/` for reviewed legal and official-source
     catalogues.
  - [ ] Create `registry/aeat/modelos/` for one TOML file per supported modelo.
  - [x] Create validation commands that load every catalogue and every completed
     modelo snapshot in one run.
  - [ ] Delete or hard-quarantine hydrate write paths, casilla corpus writers,
     schema cache writers, BOE extraction writers, export module generation,
     and DR fixture promotion paths from app-facing workflows.
  - [ ] Replace public app calculation entry points so they require validated
     registry snapshots before calculation, review, approval, export, or filing
     draft creation.
  - [ ] Add import-contract tests proving no filing-grade path can reach old
     ruleset registries, model-specific filing builders, generated export
     modules, or hydrate writers.
  - [ ] Add repository-wide checks that fail on process metadata, issue numbers,
     wave names, PR references, hydrate provenance, generated provenance, or
     transient development commentary inside runtime modules and registry TOML.
  - [ ] Add repository-wide remote-state checks proving live AEAT
     cross-reference code cannot post, present, sign, save server-side state,
     pay, direct debit, amend, cancel, or submit documents to AEAT.

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
  - [ ] Run registry validation, import-contract tests, model tests, filing/export
     tests, and vault checks before marking the wave complete.

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
  - [ ] Write `registry/aeat/modelos/130.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, relation, legal reference,
     source reference, and export layout.
  - [ ] Link Modelo 130 to registry-backed calculation, trace, review, approval,
     filing draft, and export workflows.
  - [ ] Verify Modelo 130 with real calculation examples, invalid inputs,
     date-axis boundaries, legal-reference checks, source-integrity checks,
     export roundtrips, and stale/contradictory registry failure cases.
  - [ ] Delete Modelo 130 old authorities in rulesets, filing builders, category
     casilla mappings, hydrate/casilla projections, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add import-contract tests proving Modelo 130 cannot be calculated or filed
     through old authorities.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 2` Modelo 111 complete implementation
  - [ ] Audit every Modelo 111 authority in rulesets, modelo metadata, casilla
     corpus, hydrate augment data, declaration extractors, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 111 model-law coverage ledger covering all revisions,
     legal withholding parameters, casillas, formulas, bindings, recipient
     counts, source artefacts, export fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for retenciones and
     ingresos a cuenta for work, professional, and related income categories.
  - [ ] Classify the Modelo 111 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/111.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [ ] Link Modelo 111 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 111 with real withholding examples, invalid inputs,
     date-axis boundaries, legal-reference checks, source-integrity checks,
     export roundtrips, and registry failure cases.
  - [ ] Delete Modelo 111 old authorities in rulesets, hydrate augment data,
     casilla projections, declaration extractor truth, duplicated metadata, and
     generated export/layout paths.
  - [ ] Add import-contract tests proving Modelo 111 cannot be calculated or filed
     through old authorities.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 3` Modelo 115 complete implementation
  - [ ] Audit every Modelo 115 authority in rulesets, modelo metadata, casilla
     corpus, rental/category mappings, declaration extractors, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 115 model-law coverage ledger covering all revisions,
     source artefacts, legal references, rental withholding casillas, formulas,
     parameters, data bindings, export fields, filing paths, tests, and old
     authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for rental withholding
     taxable bases, withholding amounts, recipient counts, and filing/export
     obligations.
  - [ ] Classify the Modelo 115 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/115.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [ ] Link Modelo 115 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 115 with real rental withholding examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 115 old authorities in rulesets, rental/category casilla
     mappings, casilla projections, declaration extractor truth, duplicated
     metadata, and generated export/layout paths.
  - [ ] Add import-contract tests proving Modelo 115 cannot be calculated or filed
     through old authorities.
  - [ ] Mark the wave complete only after full registry validation, project tests,
     and vault checks pass.

- `Wave 4` Modelo 123 complete implementation
  - [ ] Audit every Modelo 123 authority in rulesets, modelo metadata, casilla
     corpus, declaration extractors, annual-summary links, deadline logic,
     export specs, tests, manuals, BOE references, and official AEAT record
     designs.
  - [ ] Produce a Modelo 123 model-law coverage ledger covering all revisions,
     capital-income withholding bases, retentions, income-account treatment,
     casillas, formulas, source artefacts, export fields, filing paths, tests,
     and old authorities to delete.
  - [ ] Research and verify the official AEAT and BOE basis for capital income
     retentions and ingresos a cuenta.
  - [ ] Classify the Modelo 123 live AEAT cross-reference surface and add
     remote-state guard tests; no authenticated presentation, signing, payment,
     server-side save, or other AEAT write action is allowed.
  - [ ] Write `registry/aeat/modelos/123.toml` with every reviewed revision,
     casilla, formula, parameter, data binding, legal reference, source
     reference, and export layout.
  - [ ] Link Modelo 123 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 123 with real capital-income examples, invalid inputs,
     legal-reference checks, source-integrity checks, export roundtrips, and
     registry failure cases.
  - [ ] Delete Modelo 123 old authorities in rulesets, annual-summary shadow
     links, declaration extractor truth, casilla projections, duplicated
     metadata, and generated export/layout paths.
  - [ ] Add import-contract tests proving Modelo 123 cannot be calculated or filed
     through old authorities.
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
  - [ ] Link Modelo 131 to registry-backed calculation, trace, review, approval,
     filing draft, declaration parsing where relevant, and export workflows.
  - [ ] Verify Modelo 131 with real module examples, invalid inputs, date-axis
     boundaries, legal-reference checks, source-integrity checks, export
     roundtrips, and registry failure cases.
  - [ ] Delete Modelo 131 old authorities in rulesets, category/deadline
     hardcoding, casilla projections, declaration extractor truth, duplicated
     metadata, and generated export/layout paths.
  - [ ] Add import-contract tests proving Modelo 131 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 180 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 190 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 193 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 303 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 390 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 349 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 347 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 369 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 202 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 200 cannot be calculated or filed
     through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 232 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 720 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 840 cannot be filed through old
     authorities.
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
  - [ ] Add import-contract tests proving Modelo 036 cannot be filed through old
     authorities.
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
     remote-state guard tests; retired, unsupported, authenticated, or stateful
     surfaces fail closed and cannot be demoed as filing-capable.
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
  - [ ] Add import-contract tests proving Modelo 037 cannot be filed, imported, or
     validated through old authorities.
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
  - [ ] Add import-contract tests proving Modelo 100 cannot be calculated,
     parsed, reviewed, approved, exported, or filed through old authorities.
  - [ ] Mark the wave complete only after every Renta epoch, full registry
     validation, project tests, and vault checks pass.

- `Phase 5` Global teardown completion
  - [ ] Delete remaining old formula ruleset registration surfaces once every
     migrated modelo has registry-backed calculations.
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
     export roundtrips, filing workflow tests, and import-contract tests.
  - [ ] Run checks that prove no filing-grade workflow can access old authorities
     or generated legal-rule files.
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
