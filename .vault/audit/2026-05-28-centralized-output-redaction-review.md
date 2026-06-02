---
tags:
  - '#audit'
  - '#centralized-output-redaction'
date: '2026-05-28'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
  - '[[2026-05-28-centralized-output-redaction-adr]]'
  - '[[2026-05-28-centralized-output-redaction-research]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S01]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S02]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S03]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S04]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S05]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S06]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P01-S07]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S08]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S09]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S10]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S11]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S12]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S13]]'
  - '[[2026-05-28-centralized-output-redaction-W01-P02-S14]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S49]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S50]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S51]]'
---

# `centralized-output-redaction` Code Review

No HIGH/CRITICAL findings in the scoped S01 implementation.

## Scope

- `src/aeat/core/redaction/__init__.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S01.md`

## Findings

- None (all reviewed behavior remained aligned with this step’s stated target: canonical CLI redaction constants/helpers and placeholder policy).

## Residual risks

- `redact_structured_for_cli_output` currently collapses any UUID-shaped string (including non-profile/bucket/object UUIDs) to `CLI_PROFILE_ID_PLACEHOLDER`; this is privacy-safe but could increase output ambiguity for operators in non-sensitive debug paths.
- `cli.diagnostics.profile` / `cli.diagnostics.secure_objects` still emit raw values directly in this step (they are intended for later W02 migration), so centralized redaction is not yet effective for those surfaces until migration steps are implemented.

## W01.P01.S02 Review

No HIGH/CRITICAL findings in the scoped S02 implementation.

### Residual risks

- This step introduces output-policy enums/tables but does not yet wire enforcement call sites, so effective privacy behavior remains unchanged until downstream output rendering/log/error migration steps execute.
- `persisted_as` mappings (`LOG`/`ERROR`→`SensitivityClass.AUDIT`, `DIAGNOSTIC`→`SensitivityClass.DIAGNOSTIC`, `CLI_PUBLIC`→`None`) are coherent, but current policy reuse means call sites that only consume `redaction_rules` without the CLI key-aware placeholder helper can still miss profile/bucket/object-field normalization.

## W01.P01.S03 Review

No HIGH/CRITICAL findings in the scoped S03 implementation.

### Residual risks

- Canaries cover many canonical sensitive forms, but they do not yet test a mixed payload path where a sensitive UUID appears under non-canonical keys (e.g., `active_profile`/`active_bucket_id`), so potential normalization omissions for legacy/noncanonical key names are not covered at this stage.
- The new tests are narrowly focused on helper-level behavior and do not assert downstream CLI command output behavior (`_emit`/`_emit_envelope` surfaces), so plan-step sequencing still depends on subsequent W01.P02/W01.P03 integration tests to catch renderer-path regressions.

## W01.P01.S04 Review

No HIGH/CRITICAL findings in the scoped S04 implementation.

### Residual risks

- Logging still maintains a local sensitive-key list in `SCRUB_FIELD_PATTERNS`; only those keys drive key-aware assignment redaction. If central redaction policy grows keys without corresponding logging taxonomy updates, key-form leaks (e.g., `..._secret=...`, `..._token=...`) can bypass shape-only matching.
- `W01.P01.S05` (logging scrubber regression coverage) remains pending, so this step leaves a temporary verification gap for shared-rule migration effects despite `S04` being marked complete.

## W01.P01.S05 Review

No HIGH/CRITICAL findings in the scoped S05 implementation.

### Residual risks

- The new regression test proves plain-text shape redaction for NIF/URL/JWT in log message arguments, but shared-shape coverage is still thin for non-message surfaces (e.g., sensitive values in `extra` mappings/containers), so an ordering regression could reappear outside the tested tuple-argument path without immediate detection.
- Local `SCRUB_FIELD_PATTERNS` key matching remains in `src/aeat/core/logging.py`, so adding sensitive key names in the shared redaction policy without updating this local list can still create key-form blind spots unless another canary or sync step catches it.

## W01.P01.S06 Review

No HIGH/CRITICAL findings in the scoped S06 implementation.

### Residual risks

- Locale-specific output contracts could drift silently because `scrub_error_context` now applies shared redaction directly to stringified values for all non-secret keys; any translation text depending on context interpolation may change from readable values to digests/host-only URLs across all locales without a dedicated locale-coverage test at the envelope boundary.
- Error-context key taxonomy remains partially local (`_SECRET_FIELD_PATTERN`) in parallel with shared rules, so drift between the two policy surfaces can still produce inconsistent redaction only for key-based paths if one side lags an update.

## W01.P01.S07 Review

No HIGH/CRITICAL findings in the scoped S07 implementation.

### Residual risks

- The new canary set is focused on a single error class and a small set of sensitive shapes; it does not exercise mixed-context surfaces (e.g., `vars(error)` attributes merged with explicit `context`) where ordering or shape-specific redaction regressions could still occur.
- Assertions now pin specific hash tokens (`sha256:...`, `token:sha256:...`), which are brittle against rule-strategy or encoding changes and may hide broader operator-facing contract expectations (message readability vs redaction form) if redaction behavior evolves.

## W01.P02.S08 Review

No HIGH/CRITICAL findings in the scoped S08 implementation.

### Residual risks

- JSON redaction is now applied before serialization in `render_command_output`, which preserves current shape for tested project types but does not cover all typed payload shapes (e.g., mixed custom container types) in tests; regressions could still slip through where `json.dumps(..., default=_json_default)` interacts with redacted values.
- Text redaction runs only on the provided `lines` iterable; if callers provide non-string line objects, redaction will surface an unexpected `TypeError` from the renderer boundary rather than producing structured operator guidance at render time.

## W01.P02.S09 Review

No HIGH/CRITICAL findings in the scoped S09 implementation.

### Residual risks

- The new tests are stronger than previous API-level assertions, but they still validate a narrow fixture set (single payload shape, canonical key names, and one line-based path), so mixed-key or non-canonical sensitive key leakage remains possible outside covered scenarios.
- Tests do not explicitly exercise error-path preservation when JSON serialization fails after redaction, so that contract still relies on existing `OutputRenderingError` behavior from previous steps rather than new renderer-level redaction coverage.

## W01.P02.S08/S09 Focused Re-Review

HIGH findings present: yes. CRITICAL findings present: no.

CRO-001 | HIGH | JSON object member names bypass renderer redaction
`src/aeat/core/output_rendering.py` applies `redact_structured_for_cli_output(jsonable_output_payload(payload))` before serialization, but `jsonable_output_payload` preserves dictionary keys unchanged while only normalizing values. A JSON payload keyed by a profile UUID, NIF, URL, bearer token, or secure-object key therefore renders that raw sensitive string as the JSON object member name. This violates the W01.P02.S08 renderer-boundary goal to apply central redaction to JSON payloads before rendering and the ADR requirement that CLI output protect profile/bucket ids, object-key hints, tax identifiers, URLs, and tokens. The S09 tests cover sensitive values under ordinary schema keys, but they do not cover sensitive data carried as map keys, so the leak path remains unguarded.

## W01.P02.S08/S09 Follow-up Re-Review

CRO-001 status: resolved. String JSON member names carrying profile UUID, NIF, URL, bearer token, and secure-object key canaries are now redacted through `redact_structured_for_cli_output`, and focused renderer/helper tests cover that path. HIGH findings present: yes. CRITICAL findings present: no.

CRO-002 | HIGH | Redacted JSON member-name collisions silently drop entries
The CRO-001 fix redacts dict member names in `src/aeat/core/redaction/__init__.py`, but the dict comprehension collapses distinct sensitive keys to shared placeholders or shared host-only tokens. For example, two object-key members such as `wallet:a` and `wallet:b` both become `<object-key>`, so JSON rendering keeps only the last value. This preserves secrecy but violates the S08/S09 JSON shape/data-preservation contract by silently losing payload entries. Current tests include one sensitive key per redaction class, so they do not prove collision-safe behavior or detect data loss.

## W01.P02.S08/S09 Second Follow-up Re-Review

CRO-002 status: resolved. Redacted mapping-key collisions now receive deterministic suffixes (`#2`, `#3`, ...), preserving all entries while keeping raw sensitive member names out of rendered JSON. Focused helper and renderer tests cover the two-object-key collision path, and a direct three-key probe retained all values. HIGH findings present: no. CRITICAL findings present: no.

## W01.P02.S10/S11 Review

No HIGH/CRITICAL findings in the scoped S10/S11 implementation.

`emit_json_success` now enrolls success envelopes in `redact_structured_for_cli_output` before delegating to `emit_json_document`; result payloads, warnings, sensitive member names, and collision-suffixed object-key placeholders are covered by API-level roundtrip tests. `emit_json_document` remains a lower-level generic JSON writer and was not implicitly converted into a redaction boundary. The S11 test exercises the public stream-emission API rather than duplicating helper logic, parses the emitted JSON, checks envelope shape, verifies warning redaction, validates through `SchemaEnvelope`, and covers keyed-lookup collision preservation.

### Residual risks

- `emit_json_success` still inherits `emit_json_document`'s `default=str` fallback for unsupported non-schema objects. That appears unchanged for the generic JSON contract, but future hardening may want a stricter success-envelope serialization gate if this path is expected to match `render_command_output`'s fail-fast behavior.

## W01.P02.S12 Review

No HIGH/CRITICAL findings in the scoped S12 implementation.

`_emit_envelope` text mode now delegates to `render_command_output` with `format_name="text"` before calling `typer.echo`, so envelope text lines no longer bypass the central redacted renderer. JSON mode still branches to `emit_json_success`, preserving the schema-envelope path and the S10/S11 redaction behavior. The new test is a real transport-level regression: it builds a Click context, calls `_emit_envelope`, captures stdout from `typer.echo`, and asserts a profile UUID is absent from emitted text rather than duplicating the redaction helper logic.

### Residual risks

- The focused S12 test covers text-mode profile-id redaction only. JSON-mode coverage remains provided by the S10/S11 envelope tests rather than by a dedicated `_emit_envelope` JSON branch test in `test_common_output.py`.

## W01.P02.S13/S14 Review

No HIGH/CRITICAL findings in the scoped S13/S14 implementation.

Startup import-failure text now redacts the missing dependency before locale interpolation (`src/aeat/entrypoints/cli/__init__.py:330`), and the failure surface still emits through `write_stderr` before exiting with code 1 (`src/aeat/entrypoints/cli/__init__.py:325`). The error boundary keeps the existing exception taxonomy and forwarding behavior (`src/aeat/entrypoints/cli/_errors.py:220`, `src/aeat/entrypoints/cli/_errors.py:238`), while `write_stderr` applies `redact_for_cli_output` once before the normal stream write and both UTF-8/ASCII fallback branches (`src/aeat/entrypoints/cli/_errors.py:305`). Redaction errors are not swallowed; only stream reconfigure/flush and Unicode encode fallback behavior are handled as before.

The S13/S14 tests are non-tautological for the scoped surfaces: startup coverage invokes the actual fallback Typer app and asserts no raw sensitive dependency name leaks (`src/aeat/entrypoints/cli/test_workflow_surface.py:327`, `src/aeat/entrypoints/cli/test_workflow_surface.py:346`), and stderr coverage calls the production writer against real text streams while preserving cp1252/UTF-8 behavior (`src/aeat/entrypoints/cli/test_windows_encoding.py:53`, `src/aeat/entrypoints/cli/test_windows_encoding.py:68`). Locale keys are present in the canonical catalogues and `aeat.locales audit` passes for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` (`src/aeat/locales/en.yml:2228`, `src/aeat/locales/es.yml:2345`, `src/aeat/locales/ca.yml:2313`, `src/aeat/locales/hu.yml:2342`).

### Residual risks

- The S14 canary test exercises the shared stderr writer directly rather than a full decorated command failure in JSON and text modes. That is acceptable for this narrow step because `_emit_error_and_exit` has a single stderr emission path through `write_stderr`, but broader end-to-end error-boundary canaries would still improve regression coverage.

## W03.P09.S49 Review

No HIGH/CRITICAL findings in the scoped S49 implementation.

### Scope

- `src/aeat/core/redaction/__init__.py`
- `src/aeat/core/test_redaction.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S49.md`

### Review Findings

- `W03.P09.S49` checklist update in plan is now checked in-place and corresponds to the implemented test surface.
- `active_profile` is now enrolled in CLI key vocabulary in `src/aeat/core/redaction/__init__.py`, and `test_cli_output_structured_redacts_keyed_values_and_string_leaves` extends coverage to ensure it maps to `CLI_PROFILE_ID_PLACEHOLDER`.
- Repair/profile local profile-id redaction helpers were removed in favor of `redact_structured_for_cli_output`, and the command assertions in `test_config_repair_profile_cli_redacts_profile_identifiers` exercise real CLI invocations via `invoke_cached_cli` (not helper-only assertions).
- Profile vs bucket placeholders are now explicitly differentiated in `src/aeat/entrypoints/cli/_config/__init__.py` (`profile_id` -> `CLI_PROFILE_ID_PLACEHOLDER`, `bucket_id` -> `CLI_BUCKET_ID_PLACEHOLDER`) and confirmed in named-profile text/JSON assertions.

### Residual risks

- S49 coverage remains presence-based for the `--repair-manifest-status` and `--clear-active` branches (`test_config_repair_profile_cli_redacts_profile_identifiers` checks absence of UUIDs rather than exact transformed values in those branches).
- Tests do not yet assert exact redacted values for every nested field variant in `result.before` / `result.after`; schema-drift safety for nested repair payload keys still depends on the helper-level coverage in `src/aeat/core/test_redaction.py`.

### Execution Evidence

- Executed `uv run pytest -q src/aeat/entrypoints/cli/test_repair_privacy_contract.py::test_config_repair_profile_cli_redacts_profile_identifiers src/aeat/entrypoints/cli/test_repair_privacy_contract.py::test_config_repair_cli_redacts_active_profile_identifier src/aeat/core/test_redaction.py::test_cli_output_structured_redacts_keyed_values_and_string_leaves`

## W03.P09.S50 Review

No HIGH findings in the scoped S50 implementation. CRITICAL findings present: no.

### Scope

- `src/aeat/core/redaction/__init__.py`
- `src/aeat/core/test_redaction.py`
- `src/aeat/entrypoints/cli/test_output_redaction_contract.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S50.md`

### Findings

- `W03.P09.S50` is aligned with the plan: the canary matrix now lives on real `_emit` transport paths in `test_output_redaction_contract.py`, and the redaction policy now maps additional canonical assignment labels in `src/aeat/core/redaction/__init__.py` so text paths cover profile/bucket/object-key assignment semantics (lines around `95`–`113`, `355`–`363`).
- `test_cli_output_text_redacts_sensitive_canaries` in `src/aeat/core/test_redaction.py` was updated to include a profile-id and bucket-id canonical assignment form (`profile_id=...`, `bucket_id=...`), and continues to validate that URL path/query, tokens, tax identifiers, and object keys are masked while the output still contains a usable host.

### Residual risk

- `_CLI_IDENTIFIER_ASSIGNMENT_PATTERN` now only catches `[:=]`-style assignments and a bounded key vocabulary. It does not cover camelCase or alternate label forms for profile/bucket identifiers. This is acceptable for S50 if command outputs stay snake/hyphen style, but it is a low-risk regression surface for future command-output variants and should be covered by explicit matrix expansion in later W03.P10 steps.
- Tests do not assert schema-preserving behavior when non-canonical assignment labels are present in text or JSON, so this regex drift risk is not guarded until broader command-surface tests in S51+ run.

## W03.P09.S51 Review

No HIGH findings in the scoped S51 implementation. CRITICAL findings present: no.

### Scope

- `src/aeat/core/redaction/__init__.py`
- `src/aeat/core/test_redaction.py`
- `src/aeat/application/diagnostics.py`
- `src/aeat/entrypoints/cli/test_cli_workflow_verification.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S51.md`
- `.vault/audit/2026-05-28-centralized-output-redaction-review.md`

### Findings

- `active_profile` is value-aware in CLI redaction:
  - `src/aeat/core/redaction/__init__.py` no longer treats `active_profile` as a canonical ID key, and now checks whether its value is UUID-shaped before placeholdering it. This preserves operator-facing labels while masking raw profile UUIDs.
  - `src/aeat/core/test_redaction.py` exercises both paths (`active_profile=operator` untouched, UUID `active_profile` masked to `CLI_PROFILE_ID_PLACEHOLDER`), so the behavior is covered.
- Repair diagnostics redacts raw bucket/profile identity in emitted JSON/text:
  - `src/aeat/application/diagnostics.py::_repair_safe_wizard_status` and `src/aeat/application/diagnostics.py::_active_profile_storage_check` now replace non-empty raw profile identifiers with `CLI_PROFILE_ID_PLACEHOLDER` in repair output shaping.
  - `src/aeat/entrypoints/cli/test_cli_workflow_verification.py::test_config_app_round_trip_review_row_records_bucket_id` now asserts `active_profile` remains operator-visible (`operator`), while `profile_id` is redacted with `CLI_PROFILE_ID_PLACEHOLDER` and `bucket_id` with `CLI_BUCKET_ID_PLACEHOLDER`.
- Test quality and scope are not tautological for this change:
  - assertions remain transport-level and outcome-driven (`invoke_cached_cli`, parsed command payloads, and explicit expected redacted constants), not helper-mirror assertions.
  - no fake/stubbed command output behavior was introduced in these assertions.
- Plan path correction is implemented:
  - `.vault/exec/...-W03-P51.md` explicitly states the old apex workflow target is removed and current scope is `test_cli_workflow_verification.py`, matching the check list entry in the plan.
- Broad except/comment movement risk:
  - In this S51 diff, `except` blocks remain behaviorally the same; only comment reflow occurred around existing broad-exception catches. I do not see a new suppression or widened catch-set introduced here.
