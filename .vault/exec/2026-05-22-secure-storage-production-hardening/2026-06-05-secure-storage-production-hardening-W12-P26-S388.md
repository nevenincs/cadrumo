---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S388'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S388 - Close AFR-286 for review payload schemas

Scope: close `AFR-286` for `src/aeat/entrypoints/cli/_review_payloads.py` with signals
`manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_review_payloads.py` as the typed JSON contract for `review queue` and
  `review view`.
- Confirmed the module imports only the shared `BucketId` identity alias and CLI schema
  registry helpers.
- Confirmed the module does not construct storage repositories, resolve active-profile
  state, inspect manifests, open remote providers, or perform redaction-sensitive
  output rendering.
- Confirmed the remote-provider signal is only a JSON contract concern: payloads expose
  the application-projected bucket id and legal references that downstream mirrors or
  tools consume; the module does not own mirror transport.
- Confirmed strict roundtrip tests cover the row payload, queue envelope, view envelope,
  and unknown top-level key rejection.
- Closed `W12.P26.S388` through `vaultspec-core vault plan step check` and updated the
  `AFR-286` register status to `closed`.

## Outcome

`AFR-286` is closed as `remote-mirror` with no code changes. `_review_payloads.py`
remains a schema-only boundary that uses shared core identity and registered output
schema contracts.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_review_payloads.py src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No locale leaves or source files were changed for this slice.
