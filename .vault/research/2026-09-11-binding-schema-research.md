---
tags:
  - '#research'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:b8ce8558d38bcf16192bd3f59e419741c9bfc2b03b064c1ccef94fc0e9da0097'
related: []
---
# `binding-schema` research: `binding inventory and advisory route signal`

The binding-provider union has now landed across the authored corpus and domain schema, while revision delta authoring remains limited to casillas. The remaining problem is observability: a valid binding declaration does not by itself show its consumers, executable resolver, terminal origin, or temporal coherence. The `check-bindings` development signal joins raw fragments, compiler-materialised revisions, the canonical consumer projection, provider registrations, runtime resolver ownership, and exact Python references into one advisory reverse-route inventory. Its corrected canonical run measured and graded all 9,233 binding occurrences; casilla links are evidence edges, not the route population.

## Findings

### The current binding declaration is a genuine provider union

`BindingDefinition` now owns `provider: BindingProvider`, an explicit value contract, aggregation, applicability, terminal-origin expectations, authorship, and evidence. `source` survives only as a derived projection of `provider.kind`; the former stored `source + selector` pair is gone. `src/cadrumo/domain/calculations/registry/schema.py:252-310`.

`BindingProvider` is a closed Pydantic union discriminated by `kind`. The provider-registration table covers that union and joins each member to validation, allowed value channels, aggregation operations, terminal-origin classes, output shape, disposition, and route ownership. `src/cadrumo/domain/calculations/registry/binding_provider.py:73-105`; `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:182-198`; `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:393-787`.

The raw corpus measurement found 9,233 binding rows and classified every row as `provider_union`; no legacy `source + selector` row remained in the measured tree. This is a run result, not a frozen corpus invariant. `.logs/test-runs/2026-09-12/20260912T043707.363580Z-check-bindings-50452-a89f51f2/artifacts/binding-signal.json`.

### Revision delta authoring changes the consumer surface, not binding declaration ownership

A revision naming a predecessor inherits only casillas. Bindings, formulas, relations, and other schema families remain fully declared in each revision. Inherited casillas retain the binding references authored by their originating edition, so binding coherence must be evaluated against the successor revision's full binding collection after casilla materialisation. `dev/registry/compiler/_loader_internals.py:268-331`; `src/cadrumo/domain/calculations/registry/schema.py:794-840`.

The signal records authored and compiler-materialised counts and performs binding, formula, casilla, export, and structural consumer analysis on the effective revision surface. That is deliberately broader than today's casilla-only inheritance: if the materialiser later merges bindings or formulas, the signal follows the materialised result instead of silently reverting to raw fragments. The corrected run found 768 effective casilla edges, but emitted 9,233 binding-owned routes. `.logs/test-runs/2026-09-12/20260912T050542.410863Z-check-bindings-59724-67df81dd/artifacts/binding-signal.json`.

### Binding consumers are heterogeneous and must stay separate in the inventory

Casillas carry a primary `binding` and may carry reviewed `alternate_bindings`; alternates are equivalent input routes whose simultaneous values must agree, not precedence fallbacks or additional summands. Other binding references occur in constructs, formulas, export layouts, and application code. The signal keeps three surfaces separate: the typed `binding_consumers()` projection, a generic structural walk that also exposes constructs and schema drift, and exact Python literals that remain advisory evidence. The corrected run found 9,116 typed references and 8,474 structural references: 6,235 export layouts, 1,245 constructs, 768 casilla edges, and 226 formula references. `src/cadrumo/domain/calculations/registry/binding_targets.py`; `dev/registry/bindings.py`.

An absence from these registry reference surfaces is advisory. Dynamic and generated references cannot be disproved by a literal scan. The unreferenced lane now classifies the population by provider disposition, provider kind, applicability, and modelo rather than emitting one homogeneous warning. The corrected population is 192: 146 `manual_input` bindings owned by the explicit `non_runtime` disposition and 46 filing-grade review candidates. Only the latter become findings.

### The reverse route distinguishes declaration, enrollment, and runtime execution

For every effective binding occurrence, the signal emits one route containing its consumers, declaration authorship and location, provider payload and value contract, registration disposition, executable resolver class and stage, terminal-origin contract, and closure failures. Static closure requires provider registration, a valid provider/value/aggregation/terminal-origin contract, and an executable registered resolver for `filing_grade`. Explicit `deferred` and `non_runtime` dispositions close into separate states. The corrected run reached 1,193 `closed_filing`, 24 `closed_deferred`, and 8,016 `closed_non_runtime`, with no open routes. This is static contract closure, not proof that taxpayer data is available.

Runtime resolver enrollment is read from `CALCULATION_ROUTE_RESOLVER_OWNERSHIP`, while provider semantics come from `BINDING_PROVIDER_REGISTRATIONS`. Failure to import either live surface becomes a named limitation rather than silently degrading to a clean result. `src/cadrumo/application/modelo/calculation_route.py:47-152`; `dev/registry/bindings.py:176-282`.

### Temporal coherence is measured without inferring semantic identity

Provider temporal members are inventoried by discriminator and relative field paths. Filing year, revision, or year fields outside the temporal member are actionable absolute-coordinate candidates. Binding identifiers use the same public `edition_token_in_identifier()` rule as the edition-delta signal. The corrected run reports zero temporal-ID candidates; the former 189 findings were range-token false positives such as `2001-2017`, not declaring-edition coupling. `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:791-875`; `dev/registry/analysis/edition_delta_status.py`; `dev/registry/bindings.py`.

### The command is advisory but operationally strict

`just check-bindings` belongs to the `check` group and runs through the shared test-run command envelope with the dedicated `binding-signal` processor. The child writes the complete JSON report to the run's `artifacts/binding-signal.json`; stdout contains bounded start and finish envelopes, and `run.json` plus `run.log` retain the standard tokenized evidence. Findings do not fail the default command. TOML parse failure or loss of the loader, provider-registration inventory, runtime-resolver inventory, or canonical consumer projection is a processing error and returns 2; `--strict` may return 1 for actionable error findings.

The corrected canonical measurement on 2026-09-12 exited 0 with 58 modelos, 128 revisions, 9,233 binding occurrences and routes, 9,116 canonical consumer references, 8,474 structural references, 3,725 exact Python references, 768 casilla edges, 46 advisory findings, zero temporal-ID candidates, zero open routes, and zero limitations. Its `run.json` contains exactly the standard `artifacts`, `cache`, `command`, `exit_status`, `finished_at`, `log`, `run_id`, `scratch`, and `started_at` fields. `.logs/test-runs/2026-09-12/20260912T050542.410863Z-check-bindings-59724-67df81dd/run.json`; `.logs/test-runs/2026-09-12/20260912T050542.410863Z-check-bindings-59724-67df81dd/artifacts/binding-signal.json`.

### Remaining design questions belong to the next signal refinement

The current reverse route proves static enrollment, not that a real filing context produces a value. A later contextual lane should instantiate representative target contexts, invoke production requirement builders without taxpayer data, compare their resolved source coordinates with the authored relative provider template, and classify availability separately. The 46 filing-grade unreferenced candidates are now the focused worklist: 30 `atribucion_member`, 8 `profile`, 5 `ledger_iva_aggregation`, 2 `ledger_irnr_income_aggregation`, and 1 `ledger_renta_income_aggregation`. They require provider-specific consumer analysis; absence of a static reference is not yet an architectural defect.

## Sources

- `src/cadrumo/domain/calculations/registry/schema.py:252-310`
- `src/cadrumo/domain/calculations/registry/schema.py:794-840`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:347-387`
- `src/cadrumo/domain/calculations/registry/binding_provider.py:73-105`
- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:182-198`
- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py:393-875`
- `src/cadrumo/domain/calculations/registry/bindings.py:423-488`
- `src/cadrumo/application/modelo/calculation_route.py:47-152`
- `dev/registry/compiler/_loader_internals.py:268-331`
- `dev/registry/bindings.py:120-164`
- `dev/registry/bindings.py:176-282`
- `dev/registry/bindings.py:514-544`
- `dev/registry/bindings.py:618-784`
- `dev/registry/bindings.py:839-888`
- `dev/test_runs/command.py:22-27`
- `dev/test_runs/command.py:1028-1039`
- `justfile:255-261`
- `.logs/test-runs/2026-09-12/20260912T043707.363580Z-check-bindings-50452-a89f51f2/run.json`
- `.logs/test-runs/2026-09-12/20260912T043707.363580Z-check-bindings-50452-a89f51f2/artifacts/binding-signal.json`
