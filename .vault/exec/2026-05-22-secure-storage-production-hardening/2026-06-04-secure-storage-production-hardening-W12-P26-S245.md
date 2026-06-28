---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S245'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s245-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S245`

Closed `AFR-143` for the registry application package.

## Description

- Reviewed `src/aeat/application/registry/__init__.py` as a registry
  inspection, filed-state verification, workbook verification, and parity
  artifact service.
- Verified filed-state reads use `FiledDeclaracionObservationStore`; the file is
  not decoded through ad hoc plaintext JSON.
- Removed the stale application-layer `master_key_provider` parameter because
  the observation store routes through the active-bucket secure-object
  repository.
- Verified plain file reads and writes are explicit registry/workbook/parity
  artifacts supplied by the operator or bundled resource roots, not profile
  bucket state.
- Replaced the invalid oracle-environment raw refusal with a localized
  `RegistryApplicationInputError` carrying structured context.
- Fixed the allowed-values source to derive from `OracleEnvironment` enum
  members instead of `typing.get_args`, which is empty for the runtime enum.
- Verified the existing locale strings through the canonical
  `python -m aeat.locales` CLI audit.
- Closed `S245` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-143` is closed as a `plaintext-exception` with `secure-object, plain-file`
signals. The registry package owns
operator-requested plaintext artifacts and read-only bundled registry loads; the
encrypted filed-observation path remains bound to the secure observation store.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/registry/__init__.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `uv run --no-sync pytest -q src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No deprecated config-init surface was introduced. The S245 code change localizes
the invalid environment refusal, removes a misleading application-layer
master-key hook, and centralizes a registry CLI fixture URL through configured
AEAT URL helpers.
