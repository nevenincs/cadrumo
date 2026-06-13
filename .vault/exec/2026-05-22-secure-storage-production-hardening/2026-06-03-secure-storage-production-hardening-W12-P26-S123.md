---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S123'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s123-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S123`

Closed `AFR-021` for the declarations Sede reader.

## Description

- Reviewed the manifest-bucket, plain-file, and remote-provider signals in `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- Classified the module as an authenticated remote mirror boundary rather than a storage backend implementation.
- Verified the browser profile binding uses the active bucket id, runtime knobs come from `Settings` or `load_settings()`, and no naked environment access is present in the reviewed file.
- Verified the temporary declaration-PDF path is parser scratch created through `mkstemp`, closed after write, and unlinked in `finally`.
- Verified submitted-file downloads are read from Playwright-provided temporary download paths and returned as captured artefact bytes rather than persisted by this module.
- Wrapped declaration-PDF scratch create, write, close, and unlink failures in unchained `SedeParseError` instances with the existing translated Sede parse message, keeping the path on the central `AeatError` hierarchy without retaining OS-path exception objects.
- Redacted declaration-PDF parser failure diagnostics by removing the expediente id from parser labels and no-observation errors.
- Recorded the S123 review and updated the affected-file register row to `closed`.

## Outcome

`AFR-021` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestDeclaracionPdfObservation src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestReadOperationGuard`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py`

## Notes

The original S123 closure was a review-only classification. The continuation review found that the declaration-PDF bbox bridge should not remain on `NamedTemporaryFile(delete=False)`, so `_declarations.py` and `test_declarations.py` were subsequently changed to use a private `mkstemp` fd, assert unlink behavior, and route scratch OS failures through unchained `SedeParseError`. A follow-up reviewer pass flagged chained parser/scratch exceptions as residual privacy risk; this step closes that medium finding with redacted parser labels and a no-chained-exception regression test.

The first short-id plan CLI closure briefly flipped adjacent W12.P26 rows in the same unknown block. S124, S125, S126, S127, and S128 were reopened through the plan CLI using their full display-path identifiers before staging.
