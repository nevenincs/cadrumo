---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# W04.F03 live wallet CLI no-submit safety surfacing

## Scope

- Follow-up: `W04.F03`
- Goal: make the live IVA wallet CLI state the fail-closed representation-gate and no-AEAT-form-submission policy before an operator reaches the live route.

## Changes

- Updated `iva-wallet` group help to state the route is read-only and fail-closed before representation choices or wallet form submission.
- Updated `iva-wallet pull` help to state that no AEAT wallet forms are submitted and representation gates only continue in own-name mode.
- Updated `iva-wallet capture-history` help to state that no AEAT filing or wallet form choices are submitted.
- Added human-output safety metrics to successful `pull` and `capture-history` output: read-only fail-closed policy, own-name-only representation gate policy, and no wallet/representation choices posted.
- Added CLI surface tests for help text and pull output line construction without contacting AEAT.

## Verification

- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_pull_output_lines_name_no_submit_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_iva_history_cli_requires_live_gate_before_local_writes -q` completed with 3 passed.
- `uv run pytest src/aeat/locales/test_locale_translation_honesty.py src/aeat/application/wizard/test_wizard_translations_resolve.py -q` completed with 5 passed.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_registry_cli.py` passed.
