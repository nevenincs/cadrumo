---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S50'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P14.S50`

Propagated typed live IVA auth/acquisition outcomes through the CLI read-only
remote-state capture surface with locale-backed operator labels.

- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/entrypoints/cli/test_live_read_subgroups.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Reviewed: `.vault/audit/2026-05-28-live-iva-compensation-wallet-s50-review.md`

## Description

The live IVA wallet CLI now exposes the combined read-only
`capture-remote-state` command. The rendered report includes redacted auth
status, typed auth outcome, localized auth outcome label, provider/session
diagnostics, per-surface filed-history and wallet outcomes, and localized
per-surface outcome labels.

The backend result model already carries `LiveIvaAuthOutcome` and per-surface
`outcome_mode` values, including compatibility defaults for legacy manifests.
The S50 closure verified that the CLI consumes those fields directly rather
than inferring success from missing failures or collapsing typed auth results to
generic text.

Review follow-up added enum coverage so every current
`LiveIvaAcquisitionFailureMode` resolves to operator-facing text and future
label drift is caught by the focused CLI surface test.

## Tests

- `uv run pytest -q src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/test_iva_remote_state_acquisition.py -q` — passed, 27 tests.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/__init__.py` — passed.
- `uv run python -m aeat.locales audit` — currently blocked by unrelated shared-worktree locale drift for `errors.internal.internal_profile_keys_registration`; S50-owned live IVA locale keys are present in the supported locale files.
