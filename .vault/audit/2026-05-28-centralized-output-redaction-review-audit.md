---
tags:
  - '#audit'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
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
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S52]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S53]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S54]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S55]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P09-S56]]'
  - '[[2026-05-28-centralized-output-redaction-W03-P10-S57]]'
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

## W03.P09.S52 Review

No HIGH findings in the scoped S52 implementation. CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/adr/2026-05-28-centralized-output-redaction-adr.md`
- `.vault/research/2026-05-28-centralized-output-redaction-research.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S52.md`

### Findings

- The W03.P09.S52 intent is met: hard-coded bucket placeholders and raw bucket-id checks are now tied to the shared redaction vocabulary (`CLI_BUCKET_ID_PLACEHOLDER`) and real CLI JSON payloads.
- Test assertions remain transport-level (`invoke_cached_cli` + parsed real CLI output) rather than helper-only or mocked output checks, so they exercise real behavior under `render_command_output`/`_emit` boundaries.
- The raw-UUID absence assertion is meaningful in this context because `bucket_id` is a UUID-style bucket routing identifier while visible row fields (`transaction_id`, `bucket_event_ids`, evidence IDs) are non-UUID domain IDs in this surface, so there is no conflation in these checks.
- Placeholder-constant usage is consistent: `CLI_BUCKET_ID_PLACEHOLDER` is now imported from the central redaction contract and used across all updated S52 expectations, which is preferred over duplicated literal strings.

### Residual risks

- `bucket_id not in json.dumps(payload, sort_keys=True)` is a broad string-scan assertion. It protects against raw UUID leakage in visible outputs, but it is weaker than a structured assertion over identifier-shaped leaves and will not catch encoding/typing anomalies that still pass string serialization.

## W03.P09.S53 Review

No HIGH findings in the scoped S53 implementation. CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_workflow_surface.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/adr/2026-05-28-centralized-output-redaction-adr.md`
- `.vault/research/2026-05-28-centralized-output-redaction-research.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S53.md`

### Findings

- W03.P09.S53 is aligned with plan intent and ADR guidance: workflow-surface expectations now rely on the shared redaction vocabulary (`CLI_PROFILE_ID_PLACEHOLDER`, `CLI_BUCKET_ID_PLACEHOLDER`) rather than local literal placeholders.
- Test assertions remain real-behavior based: the updated tests execute through `invoke_cached_cli`, parse real CLI envelopes, and assert post-render output values rather than calling redaction helpers directly.
- The raw-UUID absence check (`operator_profile_id not in json.dumps(status_payload, sort_keys=True)`) is meaningful for this surface because that payload should not expose a routing UUID and the assertion directly guards that absence.
- Placeholder constants are applied consistently in JSON workflow assertions for profile and bucket IDs, and operator-facing profile label behavior remains explicitly asserted (`active_profile == "operator"`), matching the profile-label-vs-UUID distinction in ADR.

### Residual risks

- The `json.dumps(...)` leak check is useful but broad; a future regression that emits the UUID under a non-string encoding or hidden transport path could evade this guard. A structured deep-walk assertion over identifier-shaped leaves would close that gap.

## W03.P09.S54 Review

No HIGH findings in the scoped S54 implementation. CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S54.md`
- `.vault/adr/2026-05-28-centralized-output-redaction-adr.md`
- `.vault/research/2026-05-28-centralized-output-redaction-research.md`
- `.vault/audit/2026-05-28-centralized-output-redaction-review.md`

### Findings

- The S54 plan and ADR intent is met: `test_profile_lifecycle_verbs.py` now uses `CLI_PROFILE_ID_PLACEHOLDER` (imported from `src/aeat/core/redaction/__init__.py`) instead of literal `<profile-id>` for profile-ID assertions that are rendered as mutable UUID-shaped routing identity (`target_profile_id` and `profile_id` assertions).
- Real-output visibility intent is preserved: checks for `profile\tfreshprofile`, `display_name\tSpouse`, and `display_name\tbob` continue to assert operator-facing labels remain readable while raw UUIDs are not expected.
- The new status assertions (`Status\tCreated`, `Status\tUpdated`) align with the wizard output implementation, which now writes a localized label (`application.wizard.output_labels.status`) plus localized status verb values (`wizard.commands.status.*`), and this is compatible with the test suite’s enforced English locale.

### Residual risks

- Medium risk (test coverage): `test_config_profile_duplicate_copies_to_new_id` still asserts only `target_profile_id` redaction. If that output path regresses but source output were to leak a raw UUID, this file would not catch it. This is a test-completeness gap rather than a production policy bypass and should be covered with a focused assertion for `source_profile_id`.
- Low risk (future-localization): `Status\tCreated` / `Status\tUpdated` are locale-specific text assertions. They are stable in this suite because `AEAT_OUTPUT_LANGUAGE` is forced to `en`, but they will be brittle if that fixture is changed or if a locale-specific variant is introduced in this module.

## W03.P09.S54 Follow-up Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- Scope alignment is now complete for the amended S54 state:
  - `src/aeat/core/redaction/__init__.py` applies key-aware identifier replacement before generic `redact_for_log`, then UUID and object-key token redaction. This closes the redaction-order defect surfaced in the prior pass.
  - `_CLI_IDENTIFIER_ASSIGNMENT_PATTERN` now accepts tab separators and includes `source_profile_id`/`target_profile_id`, matching the current CLI label formats in lifecycle output.
  - `src/aeat/core/test_redaction.py` now asserts placeholdering for tab-separated `target_profile_id` and `source_profile_id` lines, and for operator labels on `active_profile`.
  - `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py` now asserts both `source_profile_id` and `target_profile_id` placeholders and keeps label visibility checks (`display_name`) in duplicate/rename path assertions.
- Replacing literal placeholders with `CLI_PROFILE_ID_PLACEHOLDER` is appropriate and is now fully consistent with ADR guidance and the ADR-backed shared policy.
- The status assertions are appropriate for this module: `Status\tCreated` / `Status\tUpdated` are emitted by localized wizard output keys, and this CLI test suite currently forces English output via `OUTPUT_LANGUAGE_ENV_VAR` in `src/aeat/entrypoints/cli/conftest.py`.

### Residual risks

- The localized status assertions remain a medium test-robustness risk if the module-level language fixture is changed later, but no runtime policy bypass is indicated.
- Core structured text redaction remains broad by design (non-key values in other formats may still pass through without key-aware redaction if not matched by `_CLI_IDENTIFIER_ASSIGNMENT_PATTERN`), which is now expected to be covered in later waves (W03.P10+).

## W03.P09.S55 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S55.md`

### Findings

- S55 now covers the intended distinction between portable bundle identity and public CLI output:
  - The export helper still reads the real bucket UUID and returns it for storage assertions.
  - The export text surface is asserted to contain `CLI_PROFILE_ID_PLACEHOLDER` and not the raw bucket UUID.
  - A JSON export call asserts `result.profile_id` is the shared placeholder and the raw UUID is absent from the public payload.
  - The main import roundtrip uses JSON output and asserts the import payload is placeholdered while the active bucket and imported repositories still preserve the bundle UUID.
- Test quality remains real-behavior based. The test invokes actual CLI commands, reads the written bundle, imports into a fresh storage root, and reloads encrypted repositories. No fakes, mocks, monkeypatches, or helper-only mirror checks were introduced.
- The shared redaction vocabulary is used through `CLI_PROFILE_ID_PLACEHOLDER`, so the test is tied to the central privacy contract instead of a duplicated literal.

### Residual risks

- The raw UUID absence check on the JSON payload uses `json.dumps(..., sort_keys=True)`. This is useful as a leak guard but remains a broad string scan rather than a typed deep-walk over identifier fields.
- The collision-refusal tests were tightened during follow-up to assert raw bundle UUID absence. S56 and later import-idempotency work should continue tightening adjacent import surfaces separately.

## W03.P09.S55 Follow-up Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- The prior MEDIUM import-refusal redaction gap is closed:
  - A focused helper now asserts raw profile UUID absence for public refusal output.
  - UUID-collision refusal output now asserts the exported bundle UUID is absent.
  - Label-collision refusal output now asserts the exported bundle UUID is absent.
- Focused gates passed after the refusal-path assertions were added.

### Residual risks

- JSON public-output leak checks still use a broad `json.dumps(..., sort_keys=True)` scan. This remains a robustness gap rather than a current HIGH or CRITICAL privacy regression.

## W03.P09.S56 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/_test_privacy.py`
- `src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`
- `src/aeat/entrypoints/cli/test_profile_import_idempotency.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S56.md`

### Findings

- S56 now asserts central profile-id redaction on real import-idempotency public output:
  - Export output redaction is checked before returning the bundle UUID used for storage assertions.
  - Successful identity-preserving import output is checked in JSON mode for the shared placeholder and raw UUID absence.
  - Duplicate UUID refusals, label-collision refusals, and mutated-bundle success output now assert raw UUID absence.
  - The mutated `--label` import path now recovers the freshly minted active bucket UUID and asserts that raw UUID is absent from public output.
  - Show/list reachability checks still prove the imported profiles are operator-accessible after public output redaction.
- The new `_test_privacy` helper centralizes profile-output privacy assertions for CLI tests, reducing duplicated placeholder/raw-id checks between S55 and S56 without reimplementing redaction behavior.
- Test quality remains non-tautological: tests mutate bundle identity, import through real CLI commands, read real bundle JSON, and verify encrypted repository state through the production repository path.

### Residual risks

- The shared JSON helper still uses a broad `json.dumps(..., sort_keys=True)` raw-id absence scan. It is an effective leak guard for current payloads but not a typed deep-leaf traversal.
- The fresh UUID minted by the mutated `--label` import path is now explicitly recovered and checked. Remaining risk is limited to the broad string-scan style of the JSON leak guard.

## W03.P09.S56 Follow-up Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- The prior low fresh-UUID leak blind spot on the mutated `--label` import path is closed. The test now captures the active profile after the mutated import, verifies it is a fresh minted UUID distinct from the bundle mutation, and asserts that minted UUID is absent from public output.

## W03.P10.S57 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_modelo.py`
- `.vault/plan/2026-05-28-centralized-output-redaction-plan.md`
- `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P10-S57.md`

### Findings

- The modelo CLI test surface does not currently assert raw profile IDs, bucket IDs, or tax IDs in public output. The discovered `bucket_id="default"` occurrences are model-construction inputs, and the `perceptor_nif` strings are typed parser/domain input fixtures.
- The existing real JSON `modelo describe` output test now guards that central redaction does not inject profile or bucket placeholders into non-sensitive modelo metadata, and that the payload does not contain UUID-shaped raw identifiers.
- Two real ruff `E741` findings in the touched file were fixed by replacing ambiguous loop variable names. No noqa/pragma was introduced.
- Focused gates passed after the change.

### Residual risks

- This is a narrow guard for the current `test_modelo.py` describe surface. The next modelo work/source-mesh plan rows still need to inspect command surfaces that create, calculate, and verify work units, where identifiers are more likely to appear.

## W03.P10.S57 Follow-up Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- The prior low negative-only coverage concern is materially improved. The describe JSON guard now checks both placeholder absence and UUID-shaped raw identifier absence on the rendered payload.
- Remaining risk is scoped to surface coverage: this row covers `modelo describe`; later modelo work/source-mesh rows still need to audit create/calculate/verify output surfaces.

## W03.P10.S58-S64 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Scope

- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/workflow/_models.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- `src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py`
- `src/aeat/entrypoints/cli/test_ledger_allocate_classification.py`
- `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`
- `src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py`
- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`
- `src/aeat/entrypoints/cli/test_registry_corpus.py`

### Findings

- S58/S59 close the modelo work/source-mesh JSON contamination issue by removing temporary `DBG146` logging from the calculation path. This restores parseable JSON output without weakening the real CLI assertions.
- S60-S62 now have current evidence over real ledger allocation, validation, and UX flows: 41 tests pass and continue to exercise encrypted CLI setup rather than fake storage.
- S63 repairs a real lazy-loading gap in the IVA wallet inspector tests by importing the production wizard catalogue and project-answer persistence modules before `work create` accesses `SETUP_FLOW`. No fake catalogue or monkeypatch was introduced.
- S64 confirms non-sensitive registry corpus rows continue to render without accidental over-redaction.

### Residual risks

- The seven-file central CLI batch exceeds the local command timeout when run as one command, but each target file passes individually and the grouped ledger/error batches pass. This is a runtime-duration risk, not a current assertion failure.

## W03.P11.S65-S69 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Scope

- `src/aeat/entrypoints/cli/test_output_surface_inventory.py`
- `src/aeat/entrypoints/cli/test_error_boundary_integration.py`
- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py`
- `src/aeat/entrypoints/cli/test_error_registry_contract.py`
- `src/aeat/entrypoints/cli/test_windows_encoding.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/core/errors/registry/_domain.py`

### Findings

- S65 adds the production output-surface inventory gate and routes the touched ledger JSON output through the central envelope path.
- S66/S67 keep the CLI error boundary grounded in `AeatError` behavior: wrapped typed refusals are surfaced cleanly, while genuine unexpected exceptions still log as unexpected.
- S68 removes the `N818` suppression from the Modelo IVA wallet blocked exception by introducing `ModeloIvaWalletReconciliationBlockedError` and registering that canonical class path in the error registry. The legacy public symbol remains a compatibility alias to avoid breaking existing imports.
- S69 keeps Windows stderr rendering aligned with the current shared placeholder vocabulary.

### Residual risks

- `test_write_stderr_redacts_sensitive_canaries` still asserts the literal `profile=<profile-id>` placeholder. This is currently correct but should be revisited if the redaction vocabulary changes.

## W03.P12-S70-S73 and W04.P13-S74-S78 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- The live IVA wallet static guard, LLM redaction tests, secure-storage sensitivity policy tests, and secret-store tests carry concrete focused evidence in their step records.
- No fake provider mutation, monkeypatch shortcut, skipped test, or xfail is recorded for these rows.
- The secure-storage rows assert plaintext absence, strict record roundtrips, retention policy validation, overwrite cleanup, delete, rotate, and digest listing against the existing persistence paths.

### Residual risks

- The review did not re-run the full secure-storage/LLM batches in this closeout pass because the current code changes were in the CLI/modelo/error-registry surface. Their exec records contain prior focused evidence and no current dirty code in those target files was present in the closeout set.

## W04.P14.S79-S82 Review

HIGH findings present: no.
CRITICAL findings present: no.

### Findings

- The plan now validates with `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-28-centralized-output-redaction-plan.md`.
- W04.P14 records document closeout/index regeneration work and the feature index regeneration path.
- The mandatory code-review pass found a tracking gap, not a code safety regression; S60-S64 and S66-S69 records were backfilled with current evidence.

### Residual risks

- The diff includes broad exec-record template-comment cleanup from previous agents. This is vault metadata churn rather than product behavior, but it increases review surface and should be kept isolated to the centralized-output-redaction commit.
