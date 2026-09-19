---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:324457dedd8ac3f140694450a0ffe4dca08c498b043127c20bf4286be553281f'
related:
  - "[[2026-08-22-modelo-work-binding-architecture-reference]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
---
# `source-casilla-integration` research: `recurring discovery and enrollment of disconnected calculation sources`

The project accounts for every source already declared in `BindingSourceKind`, but it does not account for typed secure business domains that should feed a filing and have never been promoted into that taxonomy. Inventory proves this upstream blind spot; fincas and five deferred row families show it is not isolated. The evidence favors a ratcheted connectivity census and finite vertical-slice features, not a permanently open implementation plan. The ADR must settle the census boundary, closed candidate dispositions, tax-grounding gate, vertical-slice completion contract, and bounded campaign shape.

## Findings

### Existing enrollment governance closes the declared-source half, not the source-domain discovery half

Every current `BindingSourceKind` is classified as enrolled, deferred, or reserved by `build_binding_source_dispositions`, and a registry-declared novel source is rejected at calculation time. This proves that declared sources cannot silently blank; it cannot detect a secure domain that has no enum member, binding, or resolver. The completed calculation-engine-foundations plan already established enroll-or-defer discipline, so the new feature must complement rather than restate it. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:394-439`, `src/cadrumo/application/modelo/_calculation_actions.py:1664-1702`, `.vault/plan/2026-06-10-calculation-engine-foundations-plan.md:27-76`, `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md:337`.

### Inventory is the first proven upstream disconnect

The related inventory-gap reference verifies a typed encrypted inventory aggregate, supported ingress, and valuation helpers alongside M100 inventory semantics, but no `BindingSourceKind`, registry binding, resolver, or `CalculationRevision` handoff. Production readiness explicitly returns false. The existing helper's obsolete `0155` wording conflicts with current `0177`, `0181`, and `0182`, so official adjudication must precede mapping. Evidence: `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`, `src/cadrumo/application/inventory/_source_readiness.py:1-51`.

### Five declared row sources are proven end-to-end disconnects rather than hypothetical matches

`RELATED_PARTY_OPERATION`, `REFUND_OPERATION`, `DONATIVO_DONOR`, `GASTO193_CONTRIBUTOR`, and `WITHHOLDING296` are explicitly deferred. Registry bindings exist for their modelos, and typed Google Sheets row assemblers exist for all five, but the Sheets command returns observations without a durable calculation-revision handoff and no live resolver owns the sources. These are strong bootstrap-census rows: both endpoints exist, while ingress and persistence remain incomplete. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:268-283`, `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py:82-190`, `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:703-735`.

### Fincas is a high-confidence candidate but not yet a proven substitutable binding

Finca aggregates produce annual ingresos, gastos, amortization, vivienda reduction, imputed rent, and attribution from typed persisted repositories, while M100 contains a related inmueble envelope. No finca source kind or calculation consumer exists, and `fincas_source_readiness` returns false. Exact per-finca, contract, scalar, and revision mapping remains legally unresolved, so name similarity cannot promote it beyond candidate status. Evidence: `src/cadrumo/domain/fincas/_aggregates.py:85-140`, `src/cadrumo/domain/fincas/_aggregates.py:219-239`, `src/cadrumo/adapters/persistence/profile/fincas.py:51-560`, `src/cadrumo/domain/fincas/_source_readiness.py:1-51`.

### Assets and amortization are candidates requiring constraint-shape adjudication

Encrypted asset and amortization repositories exist without an asset source kind or direct calculation consumer. Their values may already belong in transaction-ledger expenses or may have a distinct filing grain; the current evidence does not prove a registry gap. They belong in the census as unclassified candidates, never as automatic implementation rows. Evidence: `src/cadrumo/adapters/persistence/profile/assets.py:112-244`.

### Candidate entry must require evidence on both sides

A candidate is eligible only when a live typed source producer or supported ingress exists, a registry destination or filing semantic is identifiable for at least one law-selected modelo revision, and evidence stronger than lexical similarity supports intended equivalence. Suitable evidence is an official legal/design reference, an existing helper intent corroborated against the live revision, or a verified worked example. This prevents automation of operator judgments and blocks unsafe numeric-casilla matching. Evidence: `dev/registry/newmodelo/checklist.py:70`, `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`.

### A closed disposition set turns continuing responsibility into auditable state

The useful states are `connected`, `connect_candidate`, `grounding_blocked`, `ingress_blocked`, `registry_blocked`, `manual_by_design`, `duplicate_or_stale`, and `not_applicable`. Each row needs an owner, grounding locator, and follow-up or expiry where blocked/deferred. Manual-by-design and deletion are valid outcomes; automation is not the default. Existing source disposition parity is the precedent for a closed, exhaustive classification. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:394-439`.

### Each accepted connection needs one canonical vertical-slice completion contract

A complete slice requires the canonical source-kind taxonomy, one typed selector validator, aggregation contract, grounded registry binding and casilla linkage, enrolled `ModeloSourceResolver`, explicit precedence/override policy, correct `CalculationSourceResolution` channel, missing-source diagnostics, source identity/fingerprint provenance, legal/source reference parity, encrypted `CalculationRevision` round trip, live operator-path anti-dormancy proof, caller-conflict proof, and replay/review/export proof where supported. The existing resolver envelope already carries scalar, enum, date, row, relation, casilla, diagnostic, and provenance channels. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:813-1027`, `src/cadrumo/domain/modelos/_calculation_revision.py:814-956`.

### The repeatable loop should be a finite bootstrap plus bounded child lifecycles

A permanent L3 plan cannot state honest completion criteria and will accumulate stale Steps. A pre-enumerated mega-plan assumes the census is complete, while an inventory-only plan fails to close the upstream blind spot. The favored shape is one finite L3 bootstrap plan that establishes the census schema, discovery instrument, closed dispositions, CI ratchet, and first inventory adjudication/slice. Later accepted candidates each receive their own research, ADR or amendment, finite plan, execution, and review. A recurring audit refreshes the census without keeping a symbolic plan open forever. This is a planning-shape recommendation; the ADR must decide it.

### The recurring gate must detect capability added outside the declared-source taxonomy

The existing enum-parity gate intentionally accepts explicit deferral forever. A complementary generated census should join loaded registry snapshots and source dispositions with typed secure repositories, application ingress, exported calculation helpers, readiness declarations, and row assemblers. CI should fail when a new declared source lacks a disposition, a repository/assembler capability appears without a census row, a deferred item lacks grounding/owner/follow-up, or a source is called connected without resolver ownership and encrypted revision round-trip proof. Manual-casilla semantic matching remains report-only because constraint shape and legal identity cannot be inferred mechanically. Evidence: `src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py:63-144`, `src/cadrumo/application/modelo/tests/test_binding_source_kind_mesh_parity.py:78-171`.

## Sources

- `2026-08-22-modelo-work-binding-architecture-reference`
- `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`
- `.vault/plan/2026-06-10-calculation-engine-foundations-plan.md:27-155`
- `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md:337`
- `src/cadrumo/application/aggregation/_source_mesh.py:268-439`
- `src/cadrumo/application/aggregation/_source_mesh.py:813-1027`
- `src/cadrumo/application/modelo/_calculation_actions.py:1664-1702`
- `src/cadrumo/application/inventory/_source_readiness.py:1-51`
- `src/cadrumo/domain/fincas/_source_readiness.py:1-51`
- `src/cadrumo/domain/fincas/_aggregates.py:85-239`
- `src/cadrumo/adapters/persistence/profile/fincas.py:51-560`
- `src/cadrumo/adapters/persistence/profile/assets.py:112-244`
- `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py:82-190`
- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:703-735`
- `src/cadrumo/domain/modelos/_calculation_revision.py:814-956`
- `src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py:63-144`
- `src/cadrumo/application/modelo/tests/test_binding_source_kind_mesh_parity.py:78-171`
- `dev/registry/newmodelo/checklist.py:70`
