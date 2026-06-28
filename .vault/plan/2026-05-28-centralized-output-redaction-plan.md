---
tags:
  - '#plan'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
tier: L3
related:
  - '[[2026-05-28-centralized-output-redaction-research]]'
  - '[[2026-05-28-centralized-output-redaction-adr]]'
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---


# `centralized-output-redaction` `centralized CLI output redaction` plan

Centralize success-output redaction so CLI text, CLI JSON, error rendering, logs, diagnostics, and observability derive privacy behavior from one redaction subsystem instead of command-local patches.

## Proposed Changes

The rollout moves privacy enforcement into the shared output rendering boundary and then enrolls every production CLI and diagnostics output file discovered by the research inventory. The plan tracks core rule ownership, transport integration, command module migration, direct-output retirement, real-behavior privacy tests, mechanical inventory gates, and API/vault documentation updates.

## Steps

## Wave `W01` - central redaction and rendering boundary

This Wave creates the central output-redaction substrate and makes the common CLI rendering helpers call it before any broad command-module cleanup begins.

### Phase `W01.P01` - core redaction policy

Define one canonical rule vocabulary for output, logging, errors, and diagnostics.

- [x] `W01.P01.S01` - add CLI-output redaction profiles and profile/bucket/object-key rules; `src/aeat/core/redaction/__init__.py`.
- [x] `W01.P01.S02` - extend sensitivity policy names for CLI public output without weakening diagnostic persistence rules; `src/aeat/core/classification/__init__.py`.
- [x] `W01.P01.S03` - add structured output-redaction tests for UUID, NIF, token, URL, and object-key canaries; `src/aeat/core/test_redaction.py`.
- [x] `W01.P01.S04` - migrate logging sensitive-key matching to shared redaction rule helpers; `src/aeat/core/logging.py`.
- [x] `W01.P01.S05` - update log scrubber regression coverage after shared rule migration; `src/aeat/core/test_logging.py`.
- [x] `W01.P01.S06` - migrate error-context scrubbing to shared redaction rule helpers; `src/aeat/core/errors/_registry.py`.
- [x] `W01.P01.S07` - update error-envelope redaction tests for shared rule behavior; `src/aeat/core/errors/test_envelope.py`.

### Phase `W01.P02` - output rendering enrollment

Make the success-output renderer the mandatory privacy boundary for text and JSON.

- [x] `W01.P02.S08` - apply central redaction to JSON payloads and text lines before rendering; `src/aeat/core/output_rendering.py`.
- [x] `W01.P02.S09` - update output-rendering tests for text and JSON redaction while preserving JSON shape; `src/aeat/core/test_output_rendering.py`.
- [x] `W01.P02.S10` - route JSON-envelope success emission through the central output redaction path; `src/aeat/core/json_contract.py`.
- [x] `W01.P02.S11` - add JSON-envelope redaction roundtrip coverage for schema-preserving payloads; `src/aeat/core/test_json_envelope_roundtrip.py`.
- [x] `W01.P02.S12` - route `_emit` and `_emit_envelope` through the redacted renderer only; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W01.P02.S13` - preserve startup and root callback stderr behavior while composing shared redaction; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W01.P02.S14` - preserve error-boundary stderr behavior while composing shared redaction; `src/aeat/entrypoints/cli/_errors.py`.

### Phase `W01.P03` - observability alignment

Keep run-trace redaction aligned with the shared rule vocabulary.

- [x] `W01.P03.S15` - derive diagnostic run-trace rules from the shared registry without local drift; `src/aeat/core/observability/_redaction_rules.py`.
- [x] `W01.P03.S16` - verify the JSONL sink still redacts nested event payloads via shared rules; `src/aeat/core/observability/_sink.py`.
- [x] `W01.P03.S17` - verify trace and event-log storage still redacts nested payloads via shared rules; `src/aeat/core/observability/_store.py`.
- [x] `W01.P03.S18` - update sink redaction canaries for profile id, NIF, token, and URL path; `src/aeat/core/observability/test_sink_redaction.py`.
- [x] `W01.P03.S19` - update store redaction canaries for profile id, NIF, token, and URL path; `src/aeat/core/observability/test_store_redaction.py`.

## Wave `W02` - production CLI and diagnostics enrollment

This Wave removes command-local privacy assumptions from every production output module identified by the research inventory.

### Phase `W02.P04` - diagnostics direct-output migration

Move engineer diagnostics behind the same redacted output path or mark audited exceptions.

- [x] `W02.P04.S20` - migrate profile diagnostics direct `typer.echo` output to a redacted output helper; `src/aeat/diagnostics/profile.py`.
- [x] `W02.P04.S21` - migrate secure-object diagnostics direct `typer.echo` output to a redacted output helper; `src/aeat/diagnostics/secure_objects.py`.
- [x] `W02.P04.S22` - update profile diagnostics tests for centralized output redaction and canonical keys; `src/aeat/diagnostics/test_profile.py`.
- [x] `W02.P04.S23` - update secure-object diagnostics tests for centralized digest-only output; `src/aeat/diagnostics/test_secure_objects.py`.

### Phase `W02.P05` - config and auth command surfaces

Replace bespoke or implicit config/auth output redaction with the central renderer.

- [x] `W02.P05.S24` - remove repair/profile local output redactors that central output redaction supersedes; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P05.S25` - enroll Google config output payloads and token/object-key fields in central redaction; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W02.P05.S26` - enroll profile-census bucket/profile identifiers in central redaction; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [x] `W02.P05.S27` - replace auth diagnostic bespoke refs with shared redaction composition; `src/aeat/application/auth/_diagnostics.py`.
- [x] `W02.P05.S28` - replace auth operator preflight bespoke identity redaction with shared redaction composition; `src/aeat/application/auth/_operator.py`.
- [x] `W02.P05.S29` - update auth diagnostic tests for shared redaction behavior; `src/aeat/application/auth/test_diagnostics.py`.
- [x] `W02.P05.S30` - update auth operator tests for shared redaction behavior; `src/aeat/application/auth/test_operator.py`.

### Phase `W02.P06` - app command surfaces

Enroll the high-volume application command modules that emit profile, bucket, tax, token, and URL context.

- [x] `W02.P06.S31` - enroll live-read CLI output and auth preflight lines in central redaction; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W02.P06.S32` - enroll ledger CLI profile and bucket output in central redaction; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P06.S33` - enroll modelo CLI profile, bucket, tax, and token output in central redaction; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P06.S34` - enroll overview CLI profile and bucket output in central redaction; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W02.P06.S35` - enroll overview rendering profile display fallbacks in central redaction; `src/aeat/entrypoints/cli/_overview_rendering.py`.
- [x] `W02.P06.S36` - enroll review CLI bucket output in central redaction; `src/aeat/entrypoints/cli/_review.py`.
- [x] `W02.P06.S37` - enroll registry corpus CLI output and keep non-sensitive registry rows unchanged; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W02.P06.S38` - enroll public registry CLI output and keep non-sensitive registry rows unchanged; `src/aeat/entrypoints/cli/registry.py`.
- [x] `W02.P06.S39` - enroll root landing active-profile display behavior in central redaction; `src/aeat/entrypoints/cli/_root_landing.py`.

### Phase `W02.P07` - payload and schema helpers

Keep typed payload helpers and schema metadata compatible with centralized output redaction.

- [x] `W02.P07.S40` - classify schema helper output fields that may carry sensitive values; `src/aeat/entrypoints/cli/_schemas.py`.
- [x] `W02.P07.S41` - classify modelo payload helper fields that may carry sensitive values; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W02.P07.S42` - classify review payload helper fields that may carry sensitive values; `src/aeat/entrypoints/cli/_review_payloads.py`.
- [x] `W02.P07.S43` - preserve JSON schema conformance after redaction wrappers; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W02.P07.S44` - preserve review payload roundtrips after redaction wrappers; `src/aeat/entrypoints/cli/test_review_payloads_roundtrip.py`.

### Phase `W02.P08` - application diagnostics and repair models

Move diagnostic report shaping toward shared policy while preserving useful operator summaries.

- [x] `W02.P08.S45` - compose config-repair report redaction through the central output policy; `src/aeat/application/diagnostics.py`.
- [x] `W02.P08.S46` - compose repair-integrity row and namespace output through shared redaction semantics; `src/aeat/application/repair_integrity.py`.
- [x] `W02.P08.S47` - classify active-profile health fields as internal identifiers or operator display labels; `src/aeat/application/workflow/_profile_health.py`.
- [x] `W02.P08.S48` - keep live IVA acquisition summaries redacted through shared policy; `src/aeat/application/live/__init__.py`.

## Wave `W03` - privacy gates and broad regression coverage

This Wave adds real-behavior gates so future output surfaces cannot bypass the central boundary.

### Phase `W03.P09` - CLI privacy tests

Add operator-facing canary tests across text and JSON output.

- [x] `W03.P09.S49` - extend repair privacy coverage to assert central redaction rather than local helper behavior; `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`.
- [x] `W03.P09.S50` - add a command-output canary matrix for profile id, bucket id, tax id, URL, token, and object key; `src/aeat/entrypoints/cli/test_output_redaction_contract.py`.
- [x] `W03.P09.S51` - update workflow-verification output tests where raw ids become placeholders or digests; `src/aeat/entrypoints/cli/test_cli_workflow_verification.py`.
- [x] `W03.P09.S52` - update CLI surface tests where raw ids become placeholders or digests; `src/aeat/entrypoints/cli/test_cli_surface.py`.
- [x] `W03.P09.S53` - update workflow surface tests where raw ids become placeholders or digests; `src/aeat/entrypoints/cli/test_workflow_surface.py`.
- [x] `W03.P09.S54` - update profile lifecycle tests where raw ids become placeholders or digests; `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`.
- [x] `W03.P09.S55` - update profile import/export tests to distinguish encrypted bundle identity from public CLI output; `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`.
- [x] `W03.P09.S56` - update profile import idempotency output expectations for central redaction; `src/aeat/entrypoints/cli/test_profile_import_idempotency.py`.

### Phase `W03.P10` - domain command output tests

Update command suites whose expected output includes profile, bucket, or tax context.

- [x] `W03.P10.S57` - update modelo CLI tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W03.P10.S58` - update modelo work UX tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_modelo_work_ux.py`.
- [x] `W03.P10.S59` - update modelo source-mesh tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py`.
- [x] `W03.P10.S60` - update ledger allocation tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_ledger_allocate_classification.py`.
- [x] `W03.P10.S61` - update ledger validation tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`.
- [x] `W03.P10.S62` - update ledger UX defect tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py`.
- [x] `W03.P10.S63` - update live IVA wallet inspector tests for central redaction of identifiers; `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`.
- [x] `W03.P10.S64` - update registry corpus tests to prove non-sensitive rows remain unredacted; `src/aeat/entrypoints/cli/test_registry_corpus.py`.

### Phase `W03.P11` - error and direct-output gates

Prevent bypasses after the central boundary lands.

- [x] `W03.P11.S65` - add a production output-surface inventory gate for `_emit`, `_emit_envelope`, `typer.echo`, and direct writes; `src/aeat/entrypoints/cli/test_output_surface_inventory.py`.
- [x] `W03.P11.S66` - update error-boundary integration tests for shared error redaction behavior; `src/aeat/entrypoints/cli/test_error_boundary_integration.py`.
- [x] `W03.P11.S67` - update error-boundary unwrap tests for shared error redaction behavior; `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py`.
- [x] `W03.P11.S68` - update error-registry contract tests for shared context redaction behavior; `src/aeat/entrypoints/cli/test_error_registry_contract.py`.
- [x] `W03.P11.S69` - update Windows encoding tests to preserve redacted output rendering; `src/aeat/entrypoints/cli/test_windows_encoding.py`.

### Phase `W03.P12` - persistence and provider privacy gates

Keep non-CLI privacy tests aligned with the shared redaction vocabulary.

- [x] `W03.P12.S70` - update live IVA wallet static privacy guard for shared redaction vocabulary; `src/aeat/application/live/test_iva_wallet_privacy_static_guard.py`.
- [x] `W03.P12.S71` - update LLM redaction tests for shared redaction vocabulary; `src/aeat/adapters/outbound/llm/test_redaction.py`.
- [x] `W03.P12.S72` - update secure-storage sensitivity policy tests for shared redaction vocabulary; `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`.
- [x] `W03.P12.S73` - update secret-store tests for shared redaction vocabulary where output is inspected; `src/aeat/adapters/persistence/storage/test_secret_store.py`.

## Wave `W04` - documentation, inventory, and rollout closeout

This Wave records the architecture and leaves durable scanner/audit hooks for future changes.

### Phase `W04.P13` - API documentation

Update generated API references and operator-facing architecture notes after the implementation lands.

- [x] `W04.P13.S74` - update redaction API reference after central policy consolidation; `docs/api/aeat.core.redaction.rst`.
- [x] `W04.P13.S75` - update output-rendering API reference after rendering-time redaction lands; `docs/api/aeat.core.output_rendering.rst`.
- [x] `W04.P13.S76` - update observability API reference after rule-source consolidation lands; `docs/api/aeat.core.observability.rst`.
- [x] `W04.P13.S77` - update JSON-contract API reference after envelope redaction lands; `docs/api/aeat.core.json_contract.rst`.
- [x] `W04.P13.S78` - update CLI entrypoint API reference after output-surface enrollment lands; `docs/api/aeat.entrypoints.cli.rst`.

### Phase `W04.P14` - vault closeout

Persist the final inventory and review trail.

- [x] `W04.P14.S79` - persist before/after output-surface inventory with counts and exceptions; `.vault/audit`.
- [x] `W04.P14.S80` - persist code-review findings for the centralized output redaction rollout; `.vault/audit`.
- [x] `W04.P14.S81` - update the secure-storage hardening plan with cross-reference to this redaction rollout; `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`.
- [x] `W04.P14.S82` - update the CLI workflow index with the new output privacy boundary; `.vault/index`.

## Parallelization

Wave `W01` must land first because later command migrations depend on the shared policy and renderer. Within `W02`, config/auth, app command, payload-helper, and application-diagnostics phases can run in parallel if they keep separate files. Within `W03`, privacy gates can run in parallel by test family after `W01` is stable. `W04` waits for implementation and review.

## Verification

The plan is complete when:

- `uv run ruff check` passes for every touched path.
- `uv run pytest` passes for core redaction, logging, output rendering, error envelope, observability redaction, CLI privacy, and JSON schema conformance tests.
- `uv run -q python -m aeat.locales audit` passes if any user-facing strings change.
- The output-surface inventory test reports no unowned direct output bypasses.
- A vaultspec code review finds no HIGH or CRITICAL privacy defects.
- Every Step row is closed with a Step Record.
