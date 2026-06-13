---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S242'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s242-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S242`

Closed `AFR-140` for the operator-surface help document.

## Description

- Reviewed `src/aeat/application/operator_surface/_help.py` as backend-owned
  help/discovery metadata.
- Verified it does not read or write files, construct SQL routes, read naked
  environment variables, write storage state, or call remote providers.
- Followed up the S240 contract enrollment by adding `aeat config bucket history`
  to the config help document while leaving root help curated.
- Added localized help strings through the canonical
  `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales ...` CLI.
- Extended the operator-surface contract test to assert that config help exposes
  the bucket-history discovery command.
- Closed `S242` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-140` is closed as `manifest-discovery`. No storage migration was required:
the help module is in-memory operator discovery metadata. The CLI architecture
is more coherent because the backend-enrolled `config bucket` family now has a
localized config-help row.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_help.py src/aeat/application/operator_surface/test_contract.py`
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No deprecated `config init` surface was introduced. Root help still omits
`config bucket` deliberately; detailed config help carries the bucket-history
inspection command.
