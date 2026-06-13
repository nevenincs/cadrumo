---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S390'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S390 - Close AFR-288 for CLI schema re-export

Scope: close `AFR-288` for `src/aeat/entrypoints/cli/_schemas.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `_schemas.py` as a CLI-local re-export of the canonical
  `aeat.core.json_contract` schema registry, envelope, base classes, and emit helpers.
- Confirmed `_schemas.py` performs no storage access, active-profile lookup, settings
  resolution, environment reads, remote IO, redaction-sensitive rendering, or exception
  handling.
- Restored the JSON schema conformance gate's intended config payload registration by
  importing `_config_payloads` before comparing CLI leaves to `SCHEMA_REGISTRY`.
- Updated the zero-bare-emit gate to apply its documented exemption set after the
  config repair callback moved to `_config/_repair_cli.py`.
- Added nested config repair integrity help strings through `python -m aeat.locales`
  for `en`, `es`, `ca`, and `hu`.
- Validated validation spillover for the existing Modelo IVA wallet seed error classes:
  current HEAD already has the `ModeloError` base and centralized `ErrorCode`
  declarations instead of an ad hoc exception surface.
- Closed `W12.P26.S390` through `vaultspec-core vault plan step check` and updated the
  `AFR-288` register status to `closed`.

## Outcome

`AFR-288` is closed as `plaintext-exception`. `_schemas.py` remains a schema-contract
adapter only; persistence and secure-storage authority stay in the core JSON contract
and the command modules that emit typed envelopes.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_schemas.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_common_output.py src/aeat/entrypoints/cli/tests/test_test_envelope.py src/aeat/core/errors/registry/_domain.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_common_output.py src/aeat/entrypoints/cli/tests/test_test_envelope.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`

## Notes

The first S390 validation run exposed shared-worktree regressions outside the schema
re-export itself: a dirty cross-period clean-state implementation missing registry and
locale backing, missing IVA wallet seed registry/base hygiene, a temporarily incomplete
ledger import extraction, and config repair extraction drift. The cross-period locale
leaf was created locally through `python -m aeat.locales`, but it is not staged in this
S390 commit because the owning clean-state implementation is not in committed HEAD. The
ledger extraction and IVA wallet seed hygiene landed in the shared tree before this step
staged changes; the config repair schema/locale drift is fixed in this slice.
