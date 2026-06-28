---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S06'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W01.P02.S06 - Static live-surface mutation guards

Scope: verify static guards reject submit, push, live-write, mutation, and synthetic-Sede shortcuts in production live surfaces.

## Description

- Run command-tree guards that reject `pull-all` and `capture-all` aliases.
- Run live subgroup guards that reject submit/send/present/sign/pay/push/modify verbs.
- Run outbound Sede no-write and Renta Web Open safety tests.
- Confirm IVA wallet help still names the fail-closed no-submit policy.

## Outcome

The CLI command-tree guards pass for the live subtree and reject reintroduced `pull-all` and `capture-all` aliases. Live subgroup tests pass for filed, expedientes, notifications, justificante, verify, borrador, and IVA wallet command surfaces and reject write-shaped verbs.

Outbound Sede static tests pass for no-write surface constraints and Renta Web Open click/url safety. These tests keep write-shaped portal actions such as submit/sign/pay/present blocked from the read/navigation probes.

## Verification

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/tests/test_no_write_surface.py src/aeat/adapters/outbound/aeat/sede/tests/test_renta_web_open_safety.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_pull_help_locale_keys_do_not_use_capture_all_names src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy -q` passed with 36 selected tests.
- The earlier focused safety gate passed with 52 selected tests.

## Notes

This row did not edit production code. It verifies the guards currently present in the shared dirty worktree.
