---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S92'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# W10.P24.S92 live IVA CLI watchdog containment completed

Scope: Wave W10, Phase P24, Step S92.

## Description

- Add centralized `Settings.aeat_live_iva_cli_watchdog_timeout_ms`.
- Enroll `AEAT_LIVE_IVA_CLI_WATCHDOG_TIMEOUT_MS` in `env/.env.example`.
- Wrap the combined `iva-wallet capture-remote-state` coroutine in a CLI-level watchdog.
- Raise the existing typed live-IVA timeout error with `remote_state_command` surface metadata when the watchdog fires.
- Add local tests for typed watchdog timeout classification and subprocess canary cleanup.

## Outcome

The combined read-only IVA remote-state CLI command no longer relies solely on an outer shell/tool timeout to terminate a hung acquisition. The CLI has its own top-level watchdog budget, sourced from Settings, so cancellation happens inside the process and can run the existing asyncio/Playwright cleanup path. The subprocess canary regression runs a fresh Python child through the watchdog timeout and verifies no process with the unique canary remains afterward.

The first default was too high: the S93 reattempt proved `900000` ms exceeded the 300000 ms live retry outer timeout and still allowed a stale uv/aeat/python/Playwright/Chrome tree. S92 was reopened and corrected to `240000` ms, with a settings regression asserting the default remains below the 300000 ms operator/tool bound used for live retries.

The corrected watchdog still initially returned while leaving Chrome processes tied to a new Playwright temp profile. S92 was hardened again with an emergency reaper that snapshots preexisting Playwright temp-profile tokens and, on CLI watchdog timeout, terminates only processes carrying newly-created `playwright_chromiumdev_profile-*` tokens.

A later process inventory found a stale `capture-remote-state` command and temp-profile Chrome tree from the same read-only live retry after an earlier no-stale-process claim. That stale tree was terminated by exact command/profile match.

The latest bounded read-only retry closed the containment concern: after fresh Cl@ve auth had succeeded, `capture-remote-state` returned normally before the 300000 ms outer command timeout with an operator-timeout acquisition result, and the post-run process inventory found no matching `capture-remote-state` command, Playwright driver, or `playwright_chromiumdev_profile-*` browser process. This is process containment success only; it is not live AEAT evidence success.

Validation completed with `uv run --no-sync` because plain `uv run` attempted to resync `torch` in the shared virtualenv and hit an access-denied package lock:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_command_watchdog_reports_typed_timeout src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_watchdog_subprocess_leaves_no_canary_process src/aeat/core/test_external_constants.py::test_browser_timeouts_belong_to_settings_not_registry src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_env_example_vars_defined_in_settings -q` passed with 5 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_command_watchdog_reports_typed_timeout src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_watchdog_subprocess_leaves_no_canary_process src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_watchdog_reaps_new_playwright_temp_profile_process src/aeat/core/test_external_constants.py::test_browser_timeouts_belong_to_settings_not_registry src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_env_example_vars_defined_in_settings -q` passed with 6 tests after the emergency reaper was added.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_command_watchdog_reports_typed_timeout src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_watchdog_subprocess_leaves_no_canary_process src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_watchdog_reaps_new_playwright_temp_profile_process src/aeat/core/test_external_constants.py::test_browser_timeouts_belong_to_settings_not_registry -q` passed with 4 tests on recheck.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/core/config.py src/aeat/core/test_external_constants.py` passed.

The later retry was read-only and did not produce successful live evidence. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

This step is closed for process containment. It does not claim successful live evidence; W10.P24.S93 remains open for a read-only live retry that actually acquires filed-history and wallet evidence.
