---
tags:
  - '#research'
  - '#fact-relocation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ed11be96ec05d9c70df39cf9a3662d5b839d6b5185903ded0fb92da956c57a54'
related: []
---

# `fact-relocation` research: `residual Python-held tax facts`

The mechanical audit asks which tax-specific declarations remain embedded in Python after the `facts-registry` campaign established a governed-fact authority. The evidence supports a residual relocation campaign, not another registry: classify candidates at symbol and table granularity, reuse the existing validated `_data` and TOML authority, and leave reusable execution mechanics in Python. The governing ADR must settle this placement boundary while preserving the current formula, aggregation, binding, publication, and evidence contracts.

## Findings

### The audit is a candidate ledger, not a whole-module migration mandate

The syntax-only audit examined 1,833 eligible Python files, found 654 broad tax/legal signal files, and narrowed the direct model/legal filename set to 80 paths. It requires comparison with the active model revision before relocation and distinguishes individual declarations from the mechanisms surrounding them. Filename-based relocation would therefore produce false positives. `tmp/mechanical_module_audit.md:3-52`; `tmp/mechanical_audit_findings_index.md:1-22`.

### Residual facts cluster into six declaration families

The strongest remaining candidates are formula operands and dated applicability, source/target bindings and relations, detail-record and export layouts, verification declarations and tolerances, and typed legal decision tables. Representative findings include DT12 and SAL arithmetic, M130-to-M100 projection, M303/M390 mappings, IVA classification rules R01-R30/R99, Art. 95 selectors, M720/M721 detail fields, and XML field maps. `tmp/mechanical_audit_findings_index.md:26-108`; `tmp/mechanical_module_audit.md:193-293`.

### Python mechanisms are positive keep cases

Registry loaders and compilers, formula and predicate evaluators, aggregation folds, date arithmetic, generic prorrata and bienes mechanics, evidence reducers, row materializers, parsers, serializers, portal descriptors, and workflow orchestration remain executable mechanisms. A module may contain both retained mechanics and relocatable constants; classification must occur at symbol, table, or row level. `tmp/mechanical_module_audit.md:295-349`; `tmp/mechanical_registry_map.md:240-331`.

### The accepted facts registry already owns authority and migration lifecycle

The accepted `2026-09-09-facts-registry-governed-fact-catalogue-adr` establishes the sibling governed-fact catalogue, typed payload families, provider enrollment, exact temporal selection, provenance-bearing resolution, fail-closed behavior, migration ledgers, and adapter retirement. It also preserves the mature modelo/casilla corpus and requires classification of Python-held values. A separate registry, loader, cache, runtime authority, or generic mapping payload would conflict with that decision. `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:16-45`; `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:73-136`.

### Existing facts-registry execution owns many apparent candidates

The active facts-registry plan already covers M347, M202, maritime and family facts, Art. 20 and 52, DT12, SAL, IVA rates, invoice interpretation, treaties, deadlines, Art. 95, Art. 109 and 110, Art. 161, objective-estimation facts, external constants, and adapted category, calendar, and treaty families. Fact relocation must reconcile against those rows and accept only residual work or incomplete retirement conditions. `.vault/plan/2026-09-09-facts-registry-plan.md:60-82`; `.vault/plan/2026-09-09-facts-registry-plan.md:127-170`; `.vault/plan/2026-09-09-facts-registry-plan.md:185-236`.

### Current closure evidence narrows the immediate residual work

On 2026-09-11, unresolved facts-registry work still includes objective-estimation publication, routing aliases, adapted-family retirement, and typed IVA catalogue, place-of-supply, postal-territory, and territorial-carve-out families. Those IVA tables cannot be flattened into generic dictionaries without losing legal absence and refusal semantics. `.vault/reference/2026-09-11-facts-registry-external-constants-retirement-reference.md:15-27`; `.vault/reference/2026-09-11-facts-registry-adapted-family-normalization-reference.md:14-34`; `.vault/research/2026-09-11-facts-registry-iva-raw-authority-retirement-research.md:15-41`.

### Existing calculation and binding decisions retain mechanics in Python

Formula evaluation, aggregation, relation resolution, previous-filing selection, wallet behavior, and typed binding validation are existing reusable mechanisms. Model-specific operands, thresholds, source/target mappings, relation instances, selectors, and parameters are declarations consumed by those mechanisms. The relocation campaign must not introduce a second evaluator, resolver, aggregation path, or source kind. `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md:148-214`; `.vault/adr/2026-06-14-bindings-interface-hardening-adr.md:84-145`.

### Relocated declarations must publish through the authority artifact

The authority-artifact boundary makes the compiled, versioned authority artifact the runtime input. Raw TOML remains authoring input and cannot become a runtime fallback. Consequently, a migration is incomplete until the declaration compiles, publishes, resolves with provenance, and permits retirement of the Python duplicate. `.vault/adr/2026-09-10-registry-authority-artifact-boundary-adr.md:13-47`; `.vault/reference/2026-09-11-facts-registry-objective-estimation-publication-boundary-reference.md:14-24`.

### Alternatives narrow to a residual campaign under the existing authority

Moving entire tax-named modules is rejected because it confuses mechanics with declarations. Keeping Python tables behind a facade is useful only as explicitly tracked migration debt because it preserves parallel authority. Creating a second fact registry is rejected because the accepted catalogue already owns the lifecycle. The evidence favors a bounded residual campaign that classifies every candidate, authors only proven declarations into existing families, requests a separate schema decision for genuinely missing payload shapes, and closes bridges and duplicate paths.

### The investigation is intentionally bounded

This research does not establish the legal correctness of a candidate, prove that every audit hit executes, or authorize a new payload family. Each execution lane must re-fetch the current source and selected registry revision, preserve official evidence, and record relocate, retain, bridge, defer, or unsupported as an explicit outcome.

## Sources

- `tmp/mechanical_audit_findings_index.md:1-108`
- `tmp/mechanical_module_audit.md:3-52`
- `tmp/mechanical_module_audit.md:193-349`
- `tmp/mechanical_registry_map.md:240-331`
- `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:16-136`
- `.vault/plan/2026-09-09-facts-registry-plan.md:60-236`
- `.vault/reference/2026-09-11-facts-registry-external-constants-retirement-reference.md:15-27`
- `.vault/reference/2026-09-11-facts-registry-adapted-family-normalization-reference.md:14-34`
- `.vault/research/2026-09-11-facts-registry-iva-raw-authority-retirement-research.md:15-41`
- `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md:148-214`
- `.vault/adr/2026-06-14-bindings-interface-hardening-adr.md:84-145`
- `.vault/adr/2026-09-10-registry-authority-artifact-boundary-adr.md:13-47`
- `.vault/reference/2026-09-11-facts-registry-objective-estimation-publication-boundary-reference.md:14-24`
