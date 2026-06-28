---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S442'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S442 - Close AFR-294 for modelo projection services

Scope: close `AFR-294` for `src/aeat/application/modelo/_projection.py` with signals
`active-profile`, `manifest-bucket`, and `plain-file`; target `manifest-discovery`;
owner `W18.P38.S442`.

## Description

- Audited `src/aeat/application/modelo/_projection.py` as a split-module projection
  and comparison service.
- Confirmed the module does not construct secure-object repositories, open bucket
  manifests, read environment variables, or perform direct filesystem persistence.
- Confirmed profile-derived inputs are resolved through the active bucket id and the
  application-owned profile binding resolver rather than command-local path logic.
- Confirmed projection and comparison exceptions derive from `AeatError`, are enrolled
  in the central error registry, and use translated message keys.
- Closed `W18.P38.S442` through `vaultspec-core vault plan step check` and updated the
  `AFR-294` register status to `closed`.

## Outcome

`AFR-294` is closed as `manifest-discovery`. The module remains a read/projection
boundary over existing modelo work units, calculation revisions, bundled registry
snapshots, and profile-sourced bindings. Runtime custody stays delegated to the
repositories and profile-binding services it calls.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_projection.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py -k modelo`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required. The closeout is a register and audit correction for the
split-module affected-file wave.
