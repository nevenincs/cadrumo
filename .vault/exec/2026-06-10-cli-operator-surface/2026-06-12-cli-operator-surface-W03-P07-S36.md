---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S36'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P07.S36 Reset-Progress Operator Wording Closeout

Scope: close the residual config repair reset-progress operator-surface leak after the reset-state hard rename had already landed.

## Description

- Kept `aeat config repair reset-progress` as the live intent-named verb and kept `reset-state` retired with no alias.
- Replaced reset-progress help and curated operator descriptions with interrupted-command progress wording through `python -m aeat.locales set`.
- Changed text-mode reset-progress notices to operator-facing labels and removed the bucket id from text output while preserving the stable JSON envelope schema and `config.repair.reset_progress` registry key.
- Updated the troubleshooting how-to and regenerated the CLI reference.
- Added regression coverage for reset-progress help and text output so storage terms do not reappear in the operator surface.

## Outcome

S36 is closed. The reset-progress command no longer exposes workflow-state, envelope, fingerprint, or bucket wording in help or text-mode dry-run output. JSON payload fields remain stable for schema consumers.

## Notes

- `vaultspec-core vault plan step check` closed S36, then hit the known post-write cache invalidation `ContextVar _workspace_ctx` crash.
- Locale scaffold and audit still fail only on the unrelated existing extra key `cli.overview.warning.censo_enrolment_unverified` in all four locale files.
- Checks run: `pytest src/aeat/entrypoints/cli/_config/tests/test_repair_reset_progress.py`, `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`, `pytest dev/docs/tests/test_cli_reference_drift.py`, `ruff check` for touched Python files, `python -m aeat.locales scaffold --check`, `python -m aeat.locales audit`, `vaultspec-core vault plan check`, and scoped `git diff --check`.
