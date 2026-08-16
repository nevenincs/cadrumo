---
generated: true
tags:
  - '#index'
  - '#binding-resolver-contract-unification'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:e5c20cd4931499eca02f262159edc9f536ab6dac8ad3bb32c88ef652d5b1d32d'
related:
  - '[[2026-06-26-binding-resolver-contract-unification-P01-S01]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P01-S02]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P01-S03]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P01-S04]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P02-S05]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P02-S06]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P02-S07]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P02-S08]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P02-S09]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S10]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S11]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S12]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S13]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S14]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S19]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S20]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P03-S21]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P04-S15]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P04-S16]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P04-S17]]'
  - '[[2026-06-26-binding-resolver-contract-unification-P05-S18]]'
  - '[[2026-06-26-binding-resolver-contract-unification-adr]]'
  - '[[2026-06-26-binding-resolver-contract-unification-plan]]'
  - '[[2026-06-26-binding-resolver-contract-unification-research]]'
  - '[[2026-07-02-binding-resolver-contract-unification-audit]]'
  - '[[2026-07-04-binding-resolver-contract-unification-audit]]'
  - '[[2026-07-05-binding-resolver-contract-unification-audit]]'
---

# `binding-resolver-contract-unification` feature index

Auto-generated index of all documents tagged with `#binding-resolver-contract-unification`.

## Documents

### adr

- `2026-06-26-binding-resolver-contract-unification-adr` - `binding-resolver-contract-unification` adr: `resolver-contract unification: one source-resolver port and one result envelope across the calculate mesh` | (**status:** `accepted`)

### audit

- `2026-07-02-binding-resolver-contract-unification-audit` - `binding-resolver-contract-unification` audit: `Wave 1 D9 close-blocker audit`
- `2026-07-04-binding-resolver-contract-unification-audit` - `binding-resolver-contract-unification` audit: `S12/S14/S18 evidence review`
- `2026-07-05-binding-resolver-contract-unification-audit` - `binding-resolver-contract-unification` audit: `campaign close honesty review`

### exec

- `2026-06-26-binding-resolver-contract-unification-P01-S01` - Retire the advertised-canonical CasillaAggregation/CasillaProvenance framing from the package docstring, keeping the live ledger-aggregation classes but removing the bypassed canonical claim
- `2026-06-26-binding-resolver-contract-unification-P01-S02` - Migrate the M349-only PerModeloRegistryBindingResolution consumer onto CalculationSourceResolution, then delete the PerModeloRegistryBindingResolution model and resolve_per_modelo_registry_binding_values in the same atomic relocation commit
- `2026-06-26-binding-resolver-contract-unification-P01-S03` - Delete the consumer-less ModeloLedgerBindingAggregation model and its test after confirming zero live consumers at HEAD
- `2026-06-26-binding-resolver-contract-unification-P02-S05` - Promote the profile mesh resolver result onto CalculationSourceResolution and drop the ProfileSourcedBindingResult wrap, keeping the date-binding and provenance channels intact
- `2026-06-26-binding-resolver-contract-unification-P02-S06` - Promote the borrador mesh resolver result onto CalculationSourceResolution and drop the Modelo100BorradorBindingResult wrap, preserving the borrador_snapshot_id and bindings_sourced_from_borrador provenance trace the downstream observation builder consumes
- `2026-06-26-binding-resolver-contract-unification-P02-S07` - Enroll the profile and borrador resolvers into merge_source_resolutions with explicit mesh-merge precedence preserving the declared precedence ladder, applying the apply-cached-on-collision drive against the live peer WIP
- `2026-06-26-binding-resolver-contract-unification-P02-S08` - Remove the BindingSourceResolution Protocol and the resolve_calculation_binding_inputs B-to-A-to-B wrap, re-homing the channel-mismatch and previous-filing-override helpers onto the mesh-merged resolution, applying the apply-cached-on-collision drive against the live peer WIP
- `2026-06-26-binding-resolver-contract-unification-P02-S09` - Update the calculate orchestration call site to consume the mesh-merged resolution directly instead of CalculationBindingResolution, sourcing borrador provenance from the borrador resolution, applying the apply-cached-on-collision drive against the live peer WIP
- `2026-06-26-binding-resolver-contract-unification-P04-S15` - Author one declared disposition mapping keyed by BindingSourceKind member to its resolution state replacing the _pre_mesh_handled and _BUCKET_AGGREGATION_OWNED_SOURCES structures and the service provider enum, re-reading the LIVE mesh sets at execution time so every member carries its HEAD-at-execution disposition including r2's newly-enrolled withholding source as enrolled (not deferred), applying the apply-cached-on-collision drive against the concurrent r2 #28 withholding-enrollment and codex typing WIP
- `2026-06-26-binding-resolver-contract-unification-P04-S16` - Re-base the merge_source_resolutions enrollment and the DEFERRED_SOURCE_KINDS set onto the one disposition mapping so a member's resolution state is declared once, re-reading HEAD because r2 #28 moves the withholding source from DEFERRED_SOURCE_KINDS to live enrollment on this surface, applying the apply-cached-on-collision drive against the concurrent r2 and codex WIP
- `2026-06-26-binding-resolver-contract-unification-P04-S17` - Extend the phase-2.1 mesh parity gate to assert the disposition registry covers every BindingSourceKind member and equals the union of enrolled resolver owned_sources, reading the LIVE mesh sets at run time with no hard-coded dispositions so r2's newly-enrolled withholding source is reflected automatically, making no-dormant-source-resolvers enforceable across the union
- `2026-06-26-binding-resolver-contract-unification-P01-S04` - Drop the deleted envelopes from the aggregation package __all__ and lazy __getattr__ re-export surface in the same commits that delete them
- `2026-06-26-binding-resolver-contract-unification-P03-S10` - Author a counterpart 347/349 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_counterpart_347/349, behaviour-preserving against the existing counterpart suites
- `2026-06-26-binding-resolver-contract-unification-P03-S11` - Author a foreign-assets 720 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_foreign_assets_720, behaviour-preserving against the existing 720 suites
- `2026-06-26-binding-resolver-contract-unification-P03-S20` - Foreign-assets 720 correctness gate follow-up
- `2026-06-26-binding-resolver-contract-unification-P03-S21` - Counterpart 347/349 correctness gate follow-up
- `2026-06-26-binding-resolver-contract-unification-P03-S12` - Enroll the counterpart and foreign-assets resolvers in merge_source_resolutions and remove FOREIGN_ASSET from DEFERRED_SOURCE_KINDS now that it has a live resolver, applying the apply-cached-on-collision drive against the live peer WIP
- `2026-06-26-binding-resolver-contract-unification-P03-S13` - Collapse the retenciones double-path so the per-modelo service retenciones branch delegates to the same mesh RetencionesAggregationSourceResolver, retiring the duplicate retenciones service result type without changing the landed perceptor-count result
- `2026-06-26-binding-resolver-contract-unification-P03-S14` - Keep the CLI aggregate verb as a thin delegating projection whose aggregation delegates to the ONE mesh resolver with no re-implemented aggregation in the verb and whose persist-retencion-observations side-effect delegates to the existing single-writer observation repository with no bespoke parallel write path per composition-service-no-parallel-write-path, retiring the verb ONLY if proven to have no distinct operator purpose beyond calculate/pull and then only with the full documented-command-conformance plus how-to plus suggestion/next_action/help sweep
- `2026-06-26-binding-resolver-contract-unification-P03-S19` - Prove the retenciones collapse is behaviour-preserving by asserting the single mesh RetencionesAggregationSourceResolver reproduces the prior per-modelo-service aggregation value exactly against a 111/115/123/180/190/193 fixture, with the landed perceptor-count result unchanged and no casilla value shift
- `2026-06-26-binding-resolver-contract-unification-P05-S18` - Run the full bindings, calculate, and roundtrip test surface plus the extended disposition parity gate and confirm green with zero vestigial envelope definitions remaining and no casilla value shifted, then owner-triage the full collect-only tree

### plan

- `2026-06-26-binding-resolver-contract-unification-plan` - `binding-resolver-contract-unification` plan

### research

- `2026-06-26-binding-resolver-contract-unification-research` - `binding-resolver-contract-unification` research: `binding shape-c aggregation unification`
