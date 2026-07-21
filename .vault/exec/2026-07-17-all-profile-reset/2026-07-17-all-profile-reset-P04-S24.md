---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S24'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`

## Description

- Drive `config reset start`/`status`/`resume` through `invoke_cached_cli` against real persisted profile state (`isolated_profile_storage_root`, real bucket/modelo fixtures via `register_minimal_profile` and `ModeloRecordCatalogueRepository`).
- Assert operation-id round-tripping, `--override-retention`/`--reason` propagation, and per-target phase/summary projection through the real `ConfigResetOperationPayload` envelope.

## Outcome

Verified against HEAD (`8af409cd3f`), not re-implemented; landed by commit `38eba09021` alongside the S21 CLI door it exercises. `pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]` (file requires `-m integration` to select — a bare `pytest <file>` collects 0). Ran `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py -m integration -q --no-header`: 2 passed in 27.20s. Re-ran combined with `test_destructive_verbs_require_yes.py`: 14 passed in 15.06s, no flakes across two runs.

## Notes

No incidents. The suite is marked `integration`; a plain `pytest` invocation without `-m integration` silently collects zero tests here — worth flagging for anyone re-verifying this step casually.
