---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry filing/modelo backend` Code Review

CTR-FILING-001 | HIGH | Submission history still has plaintext JSON readers beside the new encrypted complementaria loader
The filing complementaria CLI now loads originals exclusively through `SubmissionRepository`, which resolves `<submission_id>.envelope.json`, but `SubmissionEngine.load_submission` and `SubmissionEngine.list_submissions` still resolve/read `<submission_id>.json` plaintext records under the same submissions directory. Existing submission-engine tests still write `SubmittedFiling.model_dump_json()` directly. This leaves two incompatible history stores and preserves a plaintext financial-data path for NIF, CSV, period, status, and attempt timestamps.

CTR-FILING-002 | MEDIUM | Complementaria CLI does not convert submission-load failures into a Typer parameter error
`build_complementaria_cmd` calls `_load_submission_record` before the command's application-error catch block, and `_load_submission_record` raises `SubmissionError` for not-found records. Unsafe IDs also re-enter `repository.envelope_path_for(submission_id)` inside the `except ValueError` path, re-raising the same low-level `ValueError`. Both paths bypass the command's normal `typer.BadParameter` handling.

CTR-FILING-003 | MEDIUM | Export verifier raises on malformed payloads despite its MISSING contract
`verify_export` calls `_mismatched_casillas`, which calls `parse_export_payload` without catching registry parse failures. Malformed files, literal drift, truncated payloads, bad encodings, or trailing bytes can raise `RegistryValidationError` instead of returning `DeclarationVerifyVerdict.MISSING`, even though the result model documents malformed/unreadable exports as MISSING.

CTR-FILING-004 | LOW | CLI filing tests choose any registry modelo that builds from empty inputs
`_registry_modelo_calculable_without_inputs` dynamically selects the first modelo that accepts empty inputs, and `_write_inputs` writes `{}`. The build/list/complementaria CLI tests therefore no longer pin Modelo 130 behavior and do not intentionally cover Modelo 111 either. They can pass after a registry change by exercising a different modelo than the workflow under review.

CTR-FILING-005 | LOW | Modelo 130 export test only proves at least one casilla round-trips
`test_export_writes_modelo_130_registry_layout` asserts that the set of matching exported casillas is non-empty. A layout that exports only one correct casilla and drops or corrupts the rest would still satisfy the assertion.

## Resolution

CTR-FILING-001 was resolved by routing `SubmissionEngine.load_submission` and
`SubmissionEngine.list_submissions` through `SubmissionRepository` encrypted
envelopes and updating the engine tests to persist submissions through the
repository.

CTR-FILING-002 was resolved by converting submission-load failures in the
complementaria CLI to normal Typer parameter errors and avoiding unsafe
`envelope_path_for` calls after invalid ids have already been detected.

CTR-FILING-003 was resolved by returning a `MISSING` verify result when
registry export parsing rejects a malformed payload.

CTR-FILING-004 was resolved by pinning the filing CLI positive build/list and
complementaria tests to the committed Modelo 111 registry surface instead of
selecting whichever modelo accepts empty inputs.

CTR-FILING-005 was resolved by requiring all comparable Modelo 130 exported
casillas to match the approved draft values.

Validation after fixes:

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\entrypoints\cli\filing\test_filing_cli.py src\aeat\adapters\outbound\aeat\export\test_engine.py -q` passed.
- `uv run ruff check` passed over the touched filing, export, submission-engine, and test files.
- `uv run ty check` passed over the touched filing, export, submission-engine, and test files.
