---
tags:
  - '#research'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8e3eef298663c86a17034a510d08fccba1cbf8f0e28a03f14734e7a5fefe33cd'
related: []
---
# `binding-schema` research: `revision-local binding declarations and provider union`

The question is not merely where binding files are stored, but which declaration shape the validated registry actually compiles. Current evidence shows that revision-local `bindings/*.toml` remains the enrolled authored family, while the attempted selector-union rollover stopped at source-keyed hydration around the legacy `DataBindingDefinition` envelope. The evidence favors retaining the enrolled revision-local family while replacing `source + selector` with a real, closed `provider.kind` union. A binding-specific ADR must still authorize that hard cut and settle the exact provider, temporal, value, lineage, and terminal-origin contracts.

## Findings

### Revision-local `bindings/*.toml` is enrolled, but location does not validate the current content model

The revision-fragment loader derives section ownership from the fragment directory and rejects a fragment whose table does not match that directory, so `modelos/<modelo>/revisions/<revision>/bindings/` is an active compiler input rather than an incidental archive. The compiled `ModeloRevision` still publishes `bindings: tuple[DataBindingDefinition, ...]`. These facts establish the current declaration locus, not that `DataBindingDefinition` is the desired final schema. `dev/registry/compiler/_loader_revision_fragments.py:123-137`; `src/cadrumo/domain/calculations/registry/schema.py:837-950`.

The facts-registry migration supplies a nearby typed-union precedent but explicitly excluded `ModeloRevision` and its TOML corpus. It therefore cannot be treated as implicit authorization that bindings moved into the governed-facts catalogue or acquired the same schema. `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:84-95`; `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:117-140`.

### The binding selector rollover is union-like hydration, not a closed discriminated union

`DataBindingDefinition` retains sibling `source` and `selector` fields and accepts a raw mapping at its authoring boundary. A field validator looks up the selector model from `_BINDING_SELECTOR_REGISTRY`, hydrates the mapping, and a later validator repeats selector-shape validation. The stored annotation is `SerializeAsAny[BaseModel]`, so the type itself does not enumerate its permitted members or carry a discriminator. `src/cadrumo/domain/calculations/registry/schema.py:258-299`; `src/cadrumo/domain/calculations/registry/schema.py:320-348`; `src/cadrumo/domain/calculations/registry/schema.py:386-435`; `src/cadrumo/domain/calculations/registry/schema_scalars.py:503-521`; `src/cadrumo/domain/calculations/registry/bindings.py:889-965`.

Validation and execution enrollment also remain separate: `_BINDING_VALIDATOR_REGISTRY` is independent of selector-model dispatch, while calculation-route ownership is declared again in application code. This makes a source family possible only when several structures agree, rather than because one union member owns its complete contract. `src/cadrumo/domain/calculations/registry/bindings.py:983-1078`; `src/cadrumo/application/modelo/calculation_route.py:106-203`.

By contrast, governed facts use a genuine Pydantic discriminated union and a provider-registration compiler seam. That is a useful implementation pattern, not the current binding shape. `src/cadrumo/domain/calculations/registry/facts/schema.py:376-385`; `dev/registry/compiler/fact_providers.py:52-136`.

### The current registry is a typed revision aggregate assembled from owned fragment families

The live shape is neither one monolithic TOML schema nor one universal declaration union. A revision is assembled from directory-owned fragment families into `ModeloRevision`; bindings, relations, casillas, formulas, and other families remain sibling collections. Within bindings, selector payloads are dynamically hydrated to per-source Pydantic models. Relations remain a separate provider-like declaration family and are joined back to relation-prefill bindings through binding identity. `src/cadrumo/domain/calculations/registry/schema.py:837-950`; `src/cadrumo/domain/calculations/registry/schema_surfaces.py:347-387`; `src/cadrumo/domain/calculations/registry/schema_surfaces.py:888`; `src/cadrumo/domain/calculations/registry/schema.py:618-649`.

This explains the partial-rollover symptom: the registry is declarative at the fragment-family level and typed after compilation, but binding provider semantics are split between the outer binding record, a source-indexed selector model, a separate validator dispatch, relation declarations, resolver ownership, and runtime provenance.

The physical fragmentation campaign is complete in the current corpus: 58 modelo directories contain 128 revision directories, with no single-file modelos, no single-file revisions, and no inline binding, relation, or formula sections. The loader nevertheless retains unused compatibility branches for the displaced single-file layouts. Fragment discovery and materialization are established at `dev/registry/compiler/loader_cache.py:257-355` and `dev/registry/compiler/_loader_internals.py:1057-1134`.

Runtime adds another boundary: development compilation validates TOML and publishes a digest-checked authority artifact; installed product flows reconstruct typed models from `authority.json` and do not compile TOML. `dev/registry/compiler/loader.py:1-4`; `dev/registry/compiler/authority.py:94-144`; `src/cadrumo/domain/calculations/registry/authority.py:573-616`; `src/cadrumo/domain/calculations/registry/authority_artifact.py:1-20`.

### Enrollment is complete for the fragment location and incomplete for the promised binding union

| Surface | Current enrollment |
| --- | --- |
| Revision-local `bindings/` fragments | Complete in the committed corpus and compiler-owned |
| Raw authoring selector | Still `source` plus an ordinary TOML mapping |
| Construction-time selector typing | Enrolled through source-kind dispatch into concrete Pydantic models |
| Closed source-keyed `BindingProvider` union | Not enrolled |
| Provider validation | Separately enrolled in a second dispatch table |
| Runtime route ownership | Separately enrolled in application code |
| Runtime terminal provenance | Available as a different application-owned model, not declared by provider type |
| Authoring tools | Point at revision-local bindings but still describe `DataBindingDefinition` |

The binding-vocabulary plan marked its selector-union work complete, while its own text described the work as a deferred carve. Live code resolves that contradiction: selector instances are concrete after hydration, but the stored alias remains `SerializeAsAny[BaseModel]`. `.vault/plan/2026-06-26-binding-vocabulary-cli-cohesion-plan.md:107-117`; `.vault/adr/2026-06-26-binding-vocabulary-cli-cohesion-adr.md:54-56`; `src/cadrumo/domain/calculations/registry/schema_scalars.py:515-522`.

### A true provider union should be the binding schema's principal authored axis

The strongest candidate replaces the legacy pair with one self-describing member:

```toml
[[revisions."2025".bindings]]
id = "renta-base-liquidable-negativa-general-anterior"
value = { data_type = "money", channel = "decimal" }
aggregation = { op = "copy" }
applicability = { kind = "target_periods", periods = ["0A"] }
authorship = { kind = "authored" }
legal_refs = ["ley-35-2006:art-50"]
source_refs = ["aeat-renta-2025-manual-parte1"]

[revisions."2025".bindings.provider]
kind = "previous_filing"
source_modelo = "100"
source_casilla_ids = ["1391"]
temporal = { kind = "filing_year_offset", years = -1, source_periods = ["0A"] }
```

The normalized type candidate is:

```python
class BindingDefinition(RegistryModel):
    id: BindingId
    provider: BindingProvider
    value: BindingValueContract
    aggregation: BindingAggregation
    applicability: BindingApplicability
    terminal_origins: tuple[TerminalOriginExpectation, ...]
    semantic_lineage: BindingSemanticLineage
    authorship: BindingAuthorship
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = ()
```

`BindingProvider`, temporal selection, applicability, semantic lineage, and authorship are each candidates for `Annotated[... , Field(discriminator="kind")]`. Provider membership should be derived from the currently legal registry source families, excluding mesh-only source kinds, then reconciled against the real resolver and terminal-origin inventory. `src/cadrumo/domain/calculations/registry/bindings.py:906-944`; `src/cadrumo/core/aggregation.py:230-358`.

### Binding identity, declaration occurrence, and resolved route are different records

The semantic binding ID should be timeless. Its revision occurrence is addressed by `(modelo_id, revision_id, binding_id)`, but neither revision nor concrete filing period belongs in the semantic ID. A revision-scoped provider may use a typed relative temporal expression; a concrete source year or period appears only after resolving a target filing context. Existing `BindingId` validation checks syntax and length but does not enforce this semantic invariant. `src/cadrumo/domain/calculations/registry/ids.py:21-28`.

Authored TOML should contain stable intent: semantic ID, provider template, relative temporal rule, value contract, applicability, aggregation, expected terminal-origin classes, semantic lineage, authorship lineage, and evidence. Compiler metadata should contain declaration path, ordinal, fingerprints, authority digest, reverse consumers, and generator-run identity. Runtime records should contain selected filing coordinates, resolver ID, actual provenance nodes, availability/disposition, fingerprints, and diagnostics. Existing runtime provenance already owns resolver identity, matched source coordinates, parent links, and fingerprints. `src/cadrumo/application/aggregation/source_mesh.py:618-738`; `src/cadrumo/application/aggregation/source_mesh.py:741-780`.

### The provider union cannot be declared complete until enrollment is factored into one authority

A provider member is meaningful only if code produces or retrieves its value. The candidate `BindingProviderRegistration` should join, for each provider kind, the concrete provider model, validator, allowed value/aggregation contracts, allowed terminal-origin classes, and canonical route owner or explicit non-calculation disposition. Today those facts are distributed across selector dispatch, validator dispatch, source taxonomy, and calculation-route ownership. `src/cadrumo/domain/calculations/registry/bindings.py:906-1078`; `src/cadrumo/core/aggregation.py:230-358`; `src/cadrumo/application/modelo/calculation_route.py:106-203`.

The audit consequence is a closure matrix, not one finding per binding: authored member, model member, validator enrollment, compiler acceptance, route owner, terminal-origin contract, consumer coverage, and authoring-tool support. Missing runtime observations remain availability states; they are not architectural defects unless they contradict an applicable provider contract.

### Alternatives narrow to three, with one currently favored

Keeping `source + selector` and strengthening the existing dispatch tables minimizes corpus churn, but preserves non-self-describing serialization and multi-table enrollment drift. Moving bindings into governed facts gains a real union/compiler precedent, but conflicts with the accepted facts scope and blurs a value-provider route with a governed fact. Keeping revision-local binding fragments while replacing their content with `BindingDefinition(provider=BindingProvider)` preserves the enrolled authority flow and gives the schema one typed provider axis; current evidence favors this option.

The ADR must settle whether relations become provider-union members or remain separately authored referenced definitions, the terminal-origin vocabulary, value channels beyond the current decimal/enum/date/row maps, semantic-lineage requirements, generated-authorship metadata, and the hard-cut migration of temporally named IDs. No compatibility parser should be assumed: repository policy requires atomic migration unless a released compatibility floor is explicitly established. `.codex/rules/no-legacy-compatibility.md:1-15`.

### Scope boundary and remaining measurement

This research has not yet proven an exhaustive mapping from every legal `BindingSourceKind` to a terminal-origin class, nor whether every relation-prefill declaration can be absorbed without duplicating relation semantics. It also has not adjudicated each year-bearing binding ID: a year token is a candidate temporal-coupling signal, not proof that two IDs share semantic identity. Those belong in the programmatic discovery lane and the binding-specific ADR worklist.

The present dirty checkout also cannot establish a newly published authority generation: raw fragment loading succeeds, but full authority validation has unrelated in-flight declaration failures and the bundled artifact is stale relative to the authored tree. Those conditions limit runtime-parity claims but do not change the proven loader shape. `dev/registry/compiler/validator.py:345-352`; `src/cadrumo/domain/calculations/registry/authority.py:573-616`.

## Sources

- `dev/registry/compiler/_loader_revision_fragments.py:123-137`
- `dev/registry/compiler/loader.py:1-4`
- `dev/registry/compiler/loader_cache.py:257-355`
- `dev/registry/compiler/_loader_internals.py:1057-1134`
- `dev/registry/compiler/authority.py:94-144`
- `dev/registry/compiler/validator.py:345-352`
- `src/cadrumo/domain/calculations/registry/schema.py:258-299`
- `src/cadrumo/domain/calculations/registry/schema.py:320-348`
- `src/cadrumo/domain/calculations/registry/schema.py:386-435`
- `src/cadrumo/domain/calculations/registry/schema.py:618-649`
- `src/cadrumo/domain/calculations/registry/schema.py:837-950`
- `src/cadrumo/domain/calculations/registry/schema_scalars.py:503-521`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:347-387`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:888`
- `src/cadrumo/domain/calculations/registry/bindings.py:889-1078`
- `src/cadrumo/domain/calculations/registry/facts/schema.py:376-385`
- `src/cadrumo/domain/calculations/registry/ids.py:21-28`
- `src/cadrumo/core/aggregation.py:230-358`
- `src/cadrumo/application/modelo/calculation_route.py:106-203`
- `src/cadrumo/application/aggregation/source_mesh.py:618-780`
- `src/cadrumo/domain/calculations/registry/authority.py:573-616`
- `src/cadrumo/domain/calculations/registry/authority_artifact.py:1-20`
- `dev/registry/compiler/fact_providers.py:52-136`
- `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:84-95`
- `.vault/adr/2026-09-09-facts-registry-governed-fact-catalogue-adr.md:117-140`
- `.vault/adr/2026-06-26-binding-vocabulary-cli-cohesion-adr.md:54-56`
- `.vault/plan/2026-06-26-binding-vocabulary-cli-cohesion-plan.md:107-117`
- `.codex/rules/no-legacy-compatibility.md:1-15`
