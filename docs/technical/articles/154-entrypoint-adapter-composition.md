# Entrypoint adapter composition

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-154` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This chunk covers 30 files (5,465 lines; 47,645 measured tokens) under `entrypoints`. It defines the lazy shared adapter-composition root and specialized builders for profile-bound calculation, filing, evidence, authentication, Google configuration, AEAT captures, diagnostics, and model-specific operations. These are wiring and trust-boundary modules; most business decisions are delegated to application services. The concrete adapters are referenced but not re-reviewed here.

## Product capabilities

`ProfileAdapterComposition` and its context manager provide a single place to bind persistence, identity admission, auth selection, transaction/usage-ratio repositories, evidence parsing, and related application ports for a CLI/TUI session. The root package remains inert, while child properties and function-local imports delay loading storage and outbound integrations until a command actually uses them. `ExitStack` owns the lifetime of bound dependencies and removes them on exit. Operation builders assemble groups of repositories against a selected profile bucket and, where calculations depend on taxpayer facts or tax rules, pass a retained `PinnedAuthorityOperation` through the whole bundle (shared composition (`src/cadrumo/entrypoints/adapter_composition.py`), calculation binding (`src/cadrumo/entrypoints/calculation_revision_composition.py`)).

Specialized builders connect high-impact workflows. Filing and verification receive calculation, filing, observation, workflow-gate, participation, IVA history, and ledger-membership ports. Modelo export carries a development mock software identity that is graded so generated files cannot be mistaken for presentable AEAT submissions. Censo, notification, expediente, justificante, and IVA-wallet paths translate adapter errors into application errors and persist snapshots or observations through secure repositories. Live history capture can defer artefact writes until an effect guard is acquired; wallet capture reloads stored observations and reconciliation decisions to check that persistence matches the captured result (filing bundle (`src/cadrumo/entrypoints/adapter_composition.py`), wallet reconciliation (`src/cadrumo/entrypoints/live_state_composition.py`)).

Credential and external-provider flows have explicit admission points. Google configuration binds an exact profile, checks the request identity again per run, invokes terminal admission before OAuth handoff, and uses commit/handoff callbacks around credential writes. Invoice intake runs provider admission before constructing the rate provider and again before each rate lookup. Invoice evidence composition checks the active profile, records paired consent-save callbacks, classifies off-host consent, and binds the resulting token to evidence content identity. LLM classification composition supplies local text/vision readers, evidence resolvers, run telemetry, and typed error translation; it records provider, duration, success, and error class rather than prompt contents (Google dispatch (`src/cadrumo/entrypoints/google_configuration_operation_composition.py`), invoice provider admission (`src/cadrumo/entrypoints/invoice_intake_operation_composition.py`), evidence consent (`src/cadrumo/entrypoints/invoice_evidence_operation_composition.py`), LLM composition (`src/cadrumo/entrypoints/ledger_llm_composition.py`)).

Many dedicated operation builders enforce equality between the active bucket and the immutable worker profile before composing repositories. The check is present for auth/apoderado work, invoice evidence and inspection, evidence ingestion, ledger export/linkage, M036 lifecycle, maritime preview, audit, dependency, query, and diagnostics operations. This establishes a consistent exact-profile pattern at much of the registered-operation boundary (worker check (`src/cadrumo/entrypoints/auth_apoderado_composition.py`), query boundary (`src/cadrumo/entrypoints/modelo_query_read_operation_composition.py`)).

## Security and quality assessment

The composition layer centralizes adapter selection, pinned registry/schema contexts, bucket-scoped persistence, admission callbacks, and application-facing error translation. It avoids eager imports for commands that do not touch profile data and generally shares one secure-object repository across related writes. External live readers use authenticated sessions, while receipts and state captures are represented as local evidence rather than turning this wiring layer into an AEAT write path. Taxpayer identifiers are projected into short one-way references in remote-state reports. These are useful boundaries, though runtime guarantees still depend on the secure repository and worker infrastructure outside this chunk.

One exact-profile gap is visible in the IVA live-state composition. `compose_live_state` accepts an explicit `bucket_id`, resolves storage for that ID, and does not verify that it equals the active worker bucket. The resulting `AppIvaRemoteStatePort.active_storage_span` later confirms only that the *currently active* bucket has a live storage session; the port does not retain its composed bucket ID to compare with that session. This does not prove a cross-profile read or write—the secure-object repository and application worker may independently bind access—but the local adapter boundary does not establish the same exact-bucket invariant used by neighboring operation builders. Bind and retain the bucket identity in the port and require equality before storage, or prove the repository layer makes this impossible (live-state composition (`src/cadrumo/entrypoints/live_state_composition.py`), storage guard (`src/cadrumo/entrypoints/live_state_composition.py`)).

The evidence-followup composer similarly verifies that the requested bucket is active, then returns every entry from `EvidenceConsentLedger.load_entries()` without filtering on each entry’s `profile_bucket_id`. That ledger row includes bucket identity, content address, provider/model, surface, and time, so this may expose other profiles’ consent metadata to a single-profile operation unless the application filters it after receipt. Scope the tuple in the composition boundary or verify the consumer enforces the profile filter (consent reader (`src/cadrumo/entrypoints/evidence_followup_operation_composition.py`)).

Several lower-level builders are less explicit than the registered operation wrappers. `build_justificante_capture_service(bucket_id)` binds a bucket repository without checking the active bucket, while the sibling registration builder derives the active bucket itself. `compose_ledger_action_ports` and `compose_ledger_llm` also take a bucket directly; some callers wrap them with an exact-profile check, but their own signatures do not require one. Confirm that only admitted worker paths can call these lower-level functions with profile-bound data, or put the check in the builders that serve as capability boundaries (capture service (`src/cadrumo/entrypoints/justificante_composition.py`), ledger action ports (`src/cadrumo/entrypoints/ledger_action_composition.py`), ledger LLM ports (`src/cadrumo/entrypoints/ledger_llm_composition.py`)).

## Dependencies and follow-up

These modules compose application ports over SQL/encrypted persistence, AEAT browser and document adapters, Google/LLM providers, profile custody, and compiled registry authority operations. They should be reviewed together with the operation registry and worker lifecycle, because a correct builder is only protective if every route uses it and the active-profile context cannot change between admission and use. Verify the IVA port’s exact-bucket guard, scope consent metadata to the requested bucket, and audit direct call sites for the lower-level builders noted above. Confirm the effect guard spans every irreversible file/database write and that injectable repositories always share the intended secure backend. No application or network workflow was executed; this review assesses the visible composition contracts only.

## Complete assigned-file coverage

- `src/cadrumo/entrypoints/__init__.py`
- `src/cadrumo/entrypoints/actividad_asset_composition.py`
- `src/cadrumo/entrypoints/adapter_composition.py`
- `src/cadrumo/entrypoints/auth_apoderado_composition.py`
- `src/cadrumo/entrypoints/auth_read_composition.py`
- `src/cadrumo/entrypoints/calculation_report_verification_operation_composition.py`
- `src/cadrumo/entrypoints/calculation_revision_composition.py`
- `src/cadrumo/entrypoints/calendar_evidence_composition.py`
- `src/cadrumo/entrypoints/diagnostics_operation_composition.py`
- `src/cadrumo/entrypoints/diagnostics_run_health_composition.py`
- `src/cadrumo/entrypoints/evidence_followup_operation_composition.py`
- `src/cadrumo/entrypoints/exchange_rate_composition.py`
- `src/cadrumo/entrypoints/google_configuration_operation_composition.py`
- `src/cadrumo/entrypoints/invoice_evidence_operation_composition.py`
- `src/cadrumo/entrypoints/invoice_inspection_composition.py`
- `src/cadrumo/entrypoints/invoice_intake_operation_composition.py`
- `src/cadrumo/entrypoints/justificante_composition.py`
- `src/cadrumo/entrypoints/ledger_action_composition.py`
- `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`
- `src/cadrumo/entrypoints/ledger_evidence_ingestion_operation_composition.py`
- `src/cadrumo/entrypoints/ledger_export_link_operation_composition.py`
- `src/cadrumo/entrypoints/ledger_llm_composition.py`
- `src/cadrumo/entrypoints/ledger_llm_diagnostics_composition.py`
- `src/cadrumo/entrypoints/live_borrador_operation_composition.py`
- `src/cadrumo/entrypoints/live_state_composition.py`
- `src/cadrumo/entrypoints/m036_operation_composition.py`
- `src/cadrumo/entrypoints/modelo_audit_operation_composition.py`
- `src/cadrumo/entrypoints/modelo_dependency_composition.py`
- `src/cadrumo/entrypoints/modelo_maritime_operation_composition.py`
- `src/cadrumo/entrypoints/modelo_query_read_operation_composition.py`
<!-- /preserved:article -->
