---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S406'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P31.S406`

Reconciled the repair privacy contract tests with the current supported repair CLI command surface.

- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `src/aeat/application/repair_integrity.py`

## Description

The privacy contract still asserted retired or never-landed command assumptions: `config repair integrity attribution` and `config repair plan`. The current repair app exposes `logs`, `quarantine`, `reset-state`, `profile`, `integrity objects`, `integrity registry`, `list`, and `connectivity`.

The tests now target the current supported surfaces:

- `config repair list` asserts digest-only inventory output instead of active-profile object-key hints.
- `config repair integrity objects --namespace ...` replaces the obsolete attribution route.
- `config repair quarantine --dry-run` replaces the obsolete planner surface for non-mutating metadata-only preview.
- `config repair quarantine --yes` asserts the current explicit-mutation quarantine behavior.

The repair policy command-surface catalog was also brought back into alignment with the AST-discovered CLI registry for repair, import, export, recovery, and bucket-history commands.

## Tests

Passed:

- `uv run pytest -q src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `uv run pytest -q src/aeat/entrypoints/cli/test_repair_policy_coverage.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
