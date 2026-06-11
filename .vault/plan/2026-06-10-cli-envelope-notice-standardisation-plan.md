---
tags:
  - '#plan'
  - '#cli-envelope-notice-standardisation'
date: '2026-06-10'
tier: L3
related:
  - '[[2026-06-10-cli-envelope-notice-standardisation-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: S20 -->

# `cli-envelope-notice-standardisation` `CLI notice and status standardisation burndown` plan

## Wave `W01` - Contract foundation: spine, Notice model, helper, gate

Give both envelopes a shared outer spine (schema_version, command, status, notices) and a single typed Notice channel; thread notices through the emit helper and the error boundary; extend the conformance gate. No command-group migration in this Wave.

### Phase `W01.P01` - Spine and Notice model

Author the typed Notice model and add the shared outer spine (status, notices) to SchemaEnvelope and ErrorEnvelope; remove the dead warnings field; bump schema_version once for both.

- [x] `W01.P01.S01` - Author the strict frozen Notice model (severity StrEnum info|warning, code, message, optional suggestion, optional next) and register it for reuse; `src/aeat/core/json_contract.py`.
- [x] `W01.P01.S02` - Add status and notices fields to SchemaEnvelope, remove the dead warnings field, and bump schema_version; `src/aeat/core/json_contract.py`.
- [x] `W01.P01.S03` - Add the shared outer spine (command, status=error, notices) to ErrorEnvelope while retaining the nested error body; `src/aeat/core/errors/_registry.py`.

### Phase `W01.P02` - Emit helper, error boundary, and gate

Thread notices and derived status through _emit_envelope, emit_json_success, and the error boundary; author the ModeloFinding-to-Notice projection; extend the conformance gate and add redaction roundtrip coverage.

- [x] `W01.P02.S04` - Add a notices parameter and derived status to _emit_envelope and emit_json_success and route every success emit through it; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W01.P02.S05` - Author the ModeloFinding/source-advisory to Notice projection helper consumed by command groups; `src/aeat/entrypoints/cli/_modelo_rendering.py`.
- [x] `W01.P02.S06` - Route render_error_json and render_error_text through the shared spine so the error document carries command/status/notices; `src/aeat/core/errors/_registry.py`.
- [x] `W01.P02.S07` - Extend the conformance gate to assert every emitted document carries the outer spine with a valid status value; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [x] `W01.P02.S08` - Extend the conformance gate to forbid any registered OutputSchema field that re-implements an advisory/next/suggestion outside notices; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [x] `W01.P02.S09` - Add a notices-channel redaction roundtrip test proving secret-shaped notice fields are scrubbed; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.

## Wave `W02` - Modelo advisory migration

Move the modelo calculate/verify bespoke advisory fields (source_advisories, authorization_advisory, findings, obligation advisory) onto the uniform notices channel and rebuild their text lines from the same notices so text and JSON cannot drift.

### Phase `W02.P03` - Modelo calculate and verify advisories

Migrate the modelo advisory surfaces onto notices and rebuild their operator text lines from the same notices.

- [x] `W02.P03.S10` - Migrate source_advisories on the modelo calculate result onto the notices channel and drop the bespoke payload field; `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`.
- [x] `W02.P03.S11` - Migrate authorization_advisory onto notices and remove the bespoke field from the calculate payload model; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W02.P03.S12` - Project modelo verify findings and the obligation advisory onto notices on the verify and lifecycle results; `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `W02.P03.S13` - Rebuild the advisory text lines from the projected notices so JSON and text cannot drift; `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`.

## Wave `W03` - Config/overview hint and refusal migration

Move config next-step fields and overview next-step guidance onto notices, and route the last un-enveloped refusal (no-active-profile) through the typed refusal path.

### Phase `W03.P04` - Config/overview hints and refusal

Migrate config and overview next-step hints onto notices and close the un-enveloped no-active-profile refusal.

- [x] `W03.P04.S14` - Migrate the config next-step fields onto notices and remove the bespoke next field from config payloads; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W03.P04.S15` - Migrate overview next-step guidance onto notices on the overview status result; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W03.P04.S16` - Route _active_profile_or_exit through the typed refusal path so no un-enveloped error shape remains; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W03.P04.S19` - Fix the synonym 'did you mean' suggestion hint: catch typer's vendored UsageError alongside click.UsageError in AeatTyperGroup.resolve_command so cross-path (app status to overview status) and synonym (modify to edit) hints surface again; `src/aeat/entrypoints/cli/_command_suggestions.py`.

## Wave `W04` - Sweep and closeout

Audit every success site for status correctness, run the full suite plus extended conformance gate green, and refresh generated docs plus the stale json_contract docstring.

### Phase `W04.P05` - Audit, suite, and docs

Status-correctness audit across success sites, full suite plus gate green, and generated-docs plus docstring refresh.

- [ ] `W04.P05.S17` - Audit every success emit site for correct derived status and run the full CLI suite plus extended conformance gate to green; `src/aeat/entrypoints/cli`.
- [x] `W04.P05.S18` - Refresh generated docs/api stubs and correct the stale json_contract module docstring describing bare-emit migration; `src/aeat/core/json_contract.py`.
- [x] `W04.P05.S21` - Audit complete: every CLI command module routes through _emit_envelope, no raw-JSON echo bypass, no residual bespoke advisory/next/suggestion on registered schemas, and all 46 spine/notice/error-document/redaction gate assertions green. Full-suite-green (S17) remains blocked only by two EXTERNAL peer campaigns: pull/file verb-rename register_schema drift and terminology TerminologyError(ValueError) hygiene; `src/aeat/entrypoints/cli`.
- [x] `W04.P05.S22` - Evidence: the register_schema gate is the pull/file peer campaign's ACTIVELY in-flight rename, not passive drift - peer dirty diffs edit the exact command-registration lines (reconcile_pull_verb command=modelo.reconcile, reconcile_history_verb command=modelo.reconciliation_history, iva_wallet seed/correct commands). The 13 orphan keys include peer-dirty modelo.reconcile.* and iva_wallet.* keys; `making the gate green requires editing peer-WIP files, forbidden by the absolute worktree-safety prohibition. S17 full-green is owned by that peer campaign; `src/aeat/entrypoints/cli`.

## Description

Give every CLI return document a shared outer spine and a single typed notice
channel, per the authorising ADR. The success `SchemaEnvelope` and the stderr
`ErrorEnvelope` gain common outer keys (`schema_version`, `command`, `status`,
`notices`); `status` is derived from notice severity and stays in lock-step
with the `ExitCode` table; the dead `warnings` field is removed; a strict
`Notice` model becomes the only channel for warnings, advisories, and next-step
hints. Wave W01 lands the contract, helper, error boundary, and the extended
no-allowlist conformance gate. Waves W02-W03 migrate every bespoke advisory and
next-step field (`source_advisories`, `authorization_advisory`, config `next`,
overview guidance) onto notices and close the last un-enveloped refusal. Wave
W04 audits status correctness, drives the full suite plus gate to green, and
refreshes generated docs. This continues the completed
`emit-envelope-schema-burndown` rollout using its one-Step-per-site discipline.

## Steps







## Parallelization

Waves are sequenced: W01 (the contract + helper + gate) is a hard prerequisite
for every later Wave, because the migrations in W02-W03 emit through the new
`notices=` helper and are policed by the extended gate. Within W01, P01 (model
+ envelope fields) precedes P02 (helper, boundary, gate) since the helper
imports the model. W02 and W03 are independent of each other once W01 lands and
may proceed in parallel. W04 closes after W02 and W03. Within a Phase, the
author-vs-migrate Steps follow their listed order because each migration Step
removes a field the prior Step's model edit defined.

## Verification

The plan is complete when every Step is closed and:

- `test_json_schema_conformance.py` passes, including the new outer-spine and
  no-bespoke-advisory-field assertions (no allowlist regression).
- No registered `OutputSchema` carries an advisory/`next`/`suggestion` field
  outside the `notices` channel.
- Every migrated command's rendered text output is byte-identical to its
  pre-migration output (per-command text invariant tests stay green).
- The full `src/aeat/entrypoints/cli` suite and the `aeat.core.json_contract` /
  `aeat.core.errors` suites pass.
- `python -m dev.docs.apidocs scaffold --check` is clean and the stale
  `json_contract` docstring no longer describes bare-emit migration as pending.
