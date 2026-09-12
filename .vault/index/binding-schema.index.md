---
generated: true
tags:
  - '#index'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:c54a4ea546e0026ac9be2760e1852e357597abf576c8f6c72e6c86108cc6c863'
related:
  - '[[2026-09-11-binding-schema-P01-S01]]'
  - '[[2026-09-11-binding-schema-P01-S02]]'
  - '[[2026-09-11-binding-schema-P01-S03]]'
  - '[[2026-09-11-binding-schema-P01-S04]]'
  - '[[2026-09-11-binding-schema-P01-S05]]'
  - '[[2026-09-11-binding-schema-P01-S15]]'
  - '[[2026-09-11-binding-schema-P02-S06]]'
  - '[[2026-09-11-binding-schema-P02-S07]]'
  - '[[2026-09-11-binding-schema-P02-S23]]'
  - '[[2026-09-11-binding-schema-P03-S08]]'
  - '[[2026-09-11-binding-schema-P03-S09]]'
  - '[[2026-09-11-binding-schema-P03-S10]]'
  - '[[2026-09-11-binding-schema-P03-S17]]'
  - '[[2026-09-11-binding-schema-P04-S11]]'
  - '[[2026-09-11-binding-schema-P04-S12]]'
  - '[[2026-09-11-binding-schema-P04-S13]]'
  - '[[2026-09-11-binding-schema-P04-S14]]'
  - '[[2026-09-11-binding-schema-P04-S16]]'
  - '[[2026-09-11-binding-schema-P04-S18]]'
  - '[[2026-09-11-binding-schema-P04-S19]]'
  - '[[2026-09-11-binding-schema-P04-S20]]'
  - '[[2026-09-11-binding-schema-P04-S21]]'
  - '[[2026-09-11-binding-schema-P04-S22]]'
  - '[[2026-09-11-binding-schema-P04-S24]]'
  - '[[2026-09-11-binding-schema-P04-S25]]'
  - '[[2026-09-11-binding-schema-P04-S27]]'
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-09-11-binding-schema-plan]]'
  - '[[2026-09-11-binding-schema-provider-enrollment-design-research]]'
  - '[[2026-09-11-binding-schema-research]]'
---

# `binding-schema` feature index

Auto-generated index of all documents tagged with `#binding-schema`.

## Documents

### adr

- `2026-09-11-binding-schema-adr` - `binding-schema` adr: `closed provider union and registration authority for revision-local bindings` | (**status:** `accepted`)

### exec

- `2026-09-11-binding-schema-P01-S01` - Define BindingValueContract, BindingApplicability, TerminalOriginExpectation, BindingAuthorship and the closed BindingTemporalSelector union in public defining modules
- `2026-09-11-binding-schema-P01-S15` - Enrol binding_evolutions and formula_evolutions sections on ModeloRevision through a family-agnostic IdentifierEvolution union and teach section derivation to accept closed unions
- `2026-09-11-binding-schema-P01-S02` - Convert every selector model into a provider member with a literal kind and embedded temporal member, and declare the closed BindingProvider discriminated union
- `2026-09-11-binding-schema-P01-S03` - Replace DataBindingDefinition with BindingDefinition(provider=BindingProvider) and delete BindingSelector, BindingSelectorMap, BindingSelectorValue, _coerce_selector and _validate_selector_shape
- `2026-09-11-binding-schema-P01-S04` - Introduce BindingProviderRegistration as the single enrollment authority, derive selector, validator and route lookups from it, move the import-time route invariants onto it, and register the seven unowned kinds as deferred
- `2026-09-11-binding-schema-P01-S05` - Add compiler refusals for unregistered kinds, missing model, validator or route, channel, aggregation and cardinality mismatches, unadmitted terminal origins, absolute temporal coordinates, and alternates whose value contract differs from the primary
- `2026-09-11-binding-schema-P02-S06` - Define RelationPrefillProvider carrying relation_kind, dependency_role, source modelo, casillas and one temporal member; delete RelationDefinition, RelationRevisionSelector, RelationPeriodAlignment and the relation loader section
- `2026-09-11-binding-schema-P02-S07` - Rekey RelationPrefillSourceResolver and relation queries on the binding provider instead of the relation-id join
- `2026-09-11-binding-schema-P02-S23` - Migrate persisted CalculationRevision.relation_overrides to binding-id keys through a forward, idempotent stored-data migration driven by a frozen relation-to-binding table, recompute affected revision ids and record the old-to-new pairs, with tests from every supported stored version
- `2026-09-11-binding-schema-P03-S08` - Narrow previous-filing, prorrata, bienes-inversion and iva-compensation resolvers on typed provider members and delete the Mapping-or-attr dual reads
- `2026-09-11-binding-schema-P03-S09` - Narrow ledger, oss, inventory, foreign-asset, service, profile and filing readers on typed provider members
- `2026-09-11-binding-schema-P03-S10` - Serialize the typed provider member in query projections and route alternate-binding re-splats through the canonical accessor
- `2026-09-11-binding-schema-P03-S17` - Migrate registry and application test modules that still construct legacy source/selector bindings or assert the deleted selector projection to the provider shape
- `2026-09-11-binding-schema-P04-S11` - Write the CLI-owned converter that rewrites bindings/*.toml and relations/*.toml to the provider shape, with dry-run and report modes
- `2026-09-11-binding-schema-P04-S12` - Run the converter across the corpus, delete relations fragments, replace the inventory absolute year, and republish the authority
- `2026-09-11-binding-schema-P04-S13` - Retire the ROWS exemption in favour of registration disposition, delete legacy single-file loader branches, and remove the three discriminated-union docstrings
- `2026-09-11-binding-schema-P04-S14` - Run registry verify, owning tests and import-boundary gates; record outcomes
- `2026-09-11-binding-schema-P04-S16` - Run the edition-keyed identifier rename per modelo (232, 353, 360, 720, 123, 303) ahead of that modelo's provider-shape rewrite, collapsing byte-identical cross-edition pairs to one identifier, holding 100/2025 and 303/2025 until third-party edits are committed, and confirming the edition_keyed_identifier count drops per modelo
- `2026-09-11-binding-schema-P04-S18` - Mark casilla_continuidad_evolutions as a chain family and delete every family_dispositions entry declared for it across revision.toml files in one change
- `2026-09-11-binding-schema-P04-S19` - Remediate review findings: retire no-op selector-only validators, narrow binding source accessors on provider members with explicit refusal, drop the duplicate source field from query rows, refuse cross-revision data-type disagreement in the converter and ground its family-level money rule, carry an unknown prefill coordinate as None, enforce the absolute-coordinate guard structurally in the domain, and remove the two import-invariant restatement tests
- `2026-09-11-binding-schema-P04-S20` - Make terminal-origin expectations auditable: default the expectation to the registration's permitted origin classes when a row authors none, compare the resolved provenance origin class against it at resolution, and surface a mismatch as a structured diagnostic; route the unreferenced-binding advisory into the registry status report
- `2026-09-11-binding-schema-P04-S21` - Re-derive the value contract of the 40 modelo 100 bindings whose consuming casillas omit data_type from provider-side evidence (profile field types, formula operands, resolver output channel), author the casilla data_type where it is missing, and refuse any row with no evidence
- `2026-09-11-binding-schema-P04-S22` - Ground casilla 0224's data_type against each edition's official record design and author it explicitly on every edition of the lineage, recording the wrong edition; move the boolean-on-Decimal profile bindings (anualidades-sin-minimo-descendientes, has-economic-activity and siblings) to the boolean channel with their injectors emitting bool, contract and resolver in one change
- `2026-09-11-binding-schema-P04-S24` - Make the inventory resolver emit CalculationSourceProvenance for every row binding it produces, with terminal_origin detail_record, source_ref and fingerprint, so its filing-grade rows pass the terminal-origin audit
- `2026-09-11-binding-schema-P04-S25` - Give the profile resolver and formula evaluator a real boolean channel so a declared boolean contract is never collapsed onto Decimal in transport; the modelo 100/2020 decimal casilla sweep is handed to the registry authoring lane pending the AEAT dictionary corpus
- `2026-09-11-binding-schema-P04-S27` - Extend the identifier rename tool to every id-keyed schema family (parameters, export_layouts, deadline_windows, application_links, workbook_parity_refs, constructs, verification_expectations, dependency_classifications, extraction_profiles, filing_schedules, live_cross_references, bindings, formulas), stripping edition tokens per member under the signal's year rule, rewriting every reference in the same pass, refusing collisions, and applying per modelo with the family signal line before and after

### plan

- `2026-09-11-binding-schema-plan` - `binding-schema` plan

### research

- `2026-09-11-binding-schema-provider-enrollment-design-research` - `binding-schema` research: `provider enrollment and closed binding schema design`
- `2026-09-11-binding-schema-research` - `binding-schema` research: `binding inventory and advisory route signal`
