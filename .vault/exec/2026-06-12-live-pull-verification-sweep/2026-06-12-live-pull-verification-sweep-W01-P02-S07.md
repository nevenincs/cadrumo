---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S07'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W01.P02.S07 - Operator-facing IVA evidence wording

Scope: retire or reword operator-facing remote-state vocabulary while preserving read-only pull/capture semantics.

## Description

- Rename the IVA wallet combined read CLI command from `pull-remote-state` to `pull-evidence`.
- Rename the JSON envelope command and schema id from `app.live.iva_wallet.pull_remote_state` to `app.live.iva_wallet.pull_evidence`.
- Rename the visible default output path from `iva-remote-state` to `iva-read-evidence`.
- Rename CLI watchdog timeout diagnostics from `remote_state_command` to `iva_evidence_command`.
- Update the user guide command example and text from remote-state wording to read-only IVA evidence wording.
- Preserve the backend `remote_state` service/model names as implementation vocabulary for the existing read-only acquisition code.

## Outcome

The live IVA wallet CLI now exposes the combined filed-history plus wallet read as:

- `aeat app live iva-wallet pull-evidence --from-year ... --to-year ... --target-year ... --target-period ...`

The old `pull-remote-state` command is no longer registered. Help output for `iva-wallet` lists `pull-evidence`, and `pull-evidence --help` contains no `remote-state` wording. The JSON schema and envelope command also use `pull_evidence`.

During verification, the focused watchdog tests exposed a Windows robustness issue in process inventory: PowerShell process output could fail text decoding and leave `stdout` unset before the watchdog emitted its typed timeout. The process inventory now captures bytes and decodes as UTF-8 with replacement so watchdog diagnostics remain typed.

## Verification

- `uv run pytest src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m integration -q` passed with 9 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/tests/test_parity.py -m "integration or not integration" -q` passed with 156 tests.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py docs/how-to/check-aeat-notifications.md` passed.
- `uv run aeat app live iva-wallet pull-remote-state --help` failed with `No such command 'pull-remote-state'`.
- `uv run aeat app live iva-wallet --help` passed and listed `pull-evidence`.
- `rg -n "pull-remote-state|pull_remote_state|app\\.live\\.iva_wallet\\.pull_remote_state|remote-state|remote_state_command|remote-state command" src/aeat/entrypoints/cli src/aeat/locales docs/how-to/check-aeat-notifications.md -g "*.py" -g "*.yml" -g "*.md"` found only negative test assertions.

## Notes

No authenticated AEAT pull was attempted for this wording row. The live censo/calendar environment blocker remains unchanged: full authenticated proof still requires a valid profile passphrase and a profile tax identity matching the AEAT authenticated identity.
