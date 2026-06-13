---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S388'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S388 - Close AFR-286 for review payload schemas

Scope: close `AFR-286` for `src/aeat/entrypoints/cli/_review_payloads.py` with signals
`manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `src/aeat/entrypoints/cli/_review_payloads.py` as the typed JSON envelope
  schema module for `aeat review queue` and `aeat review view`.
- Confirmed the module only defines strict `OutputSchema` payload models and registers
  the `review.queue` and `review.view` JSON contracts.
- Confirmed the bucket signal is an output field (`bucket_id`) projected from
  application review rows, not a storage route or direct repository constructor.
- Confirmed storage/provider work lives outside the payload module: `_review.py`
  delegates to `project_review_queue()` / `project_review_item()`, while application
  review aggregation uses the active bucket and bucket-bound adapters.
- Closed `W12.P26.S388` through `vaultspec-core vault plan step check` and confirmed the
  `AFR-286` register status is `closed`.

## Outcome

`AFR-286` is closed as `remote-mirror` for the payload/JSON-contract surface. The file
does not create a storage backend, open remote providers, enumerate manifests, or mutate
state. It mirrors review rows into registered CLI JSON schemas, including the bucket id
that identifies the active review context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_review_payloads.py src/aeat/entrypoints/cli/_review.py src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py src/aeat/entrypoints/cli/tests/test_review_operator_errors.py src/aeat/application/review/_operator.py src/aeat/application/review/_aggregator.py src/aeat/application/review/_adapters.py src/aeat/application/review/tests/test_adapters.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py src/aeat/entrypoints/cli/tests/test_review_operator_errors.py`
- `uv run --no-sync pytest -q -m unit src/aeat/application/review/tests/test_adapters.py src/aeat/application/review/tests/test_operator.py src/aeat/application/review/tests/test_aggregator.py src/aeat/application/review/tests/test_models.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "review payloads ReviewQueueRowPayload registered schema bucket id remote mirror manifest discovery" --type code --port 8766 --max-results 6`

## Notes

The first mixed pytest command selected only the integration-marked CLI tests and
deselected the unit-marked application review tests. The application review tests were
rerun explicitly with `-m unit` and passed with 40 tests.
