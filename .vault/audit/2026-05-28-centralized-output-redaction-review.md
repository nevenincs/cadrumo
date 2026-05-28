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
