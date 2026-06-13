---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S104'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-002 for Borrador parser entry point

## Scope

- `src/aeat/adapters/inbound/borrador/_parser.py`
- `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`

## Description

- Classify `parse_borrador` as a `plaintext-exception` inbound parser boundary.
- Confirm the parser composes artifact-kind detection and extractor selection, returns typed `BorradorObservation` data, and does not persist local side-store state or construct secure-object repositories.
- Harden parser diagnostics so they record only a stable source placeholder, artifact kind, and year without exposing filesystem-derived PDF basenames.
- Add a parser log privacy regression test that renames a generated PDF to a NIF-like filename and verifies emitted log messages do not contain that basename.

## Outcome

- `uv run pytest -q src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py` passed: 16 passed.
- `uv run --no-sync ruff check src/aeat/adapters/inbound/borrador/_parser.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py` passed.

## Notes

- Initial review found a LOW privacy issue: parser debug/info logs used `path.name`, which could expose user-identifying filenames. The step now replaces that value with `source=<input-pdf>` while preserving non-sensitive diagnostic context.
- S103 covers the concrete Modelo 100 extractor; this step closes the public parser entry point.
