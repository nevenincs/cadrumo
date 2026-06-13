---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S140'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S140 Modelo Amendment and Import Verification

Scope: verify residual modelo amendment/import extraction leaves `_actions.py` under the 1250-line budget and preserves facade-only consumers.

## Description

- Verified amendment, external import, export, filing snapshot, filing flow, and cross-period clean-state behavior after extraction.
- Verified public `aeat.application.modelo` exports and legacy private `_actions.py` compatibility aliases resolve to the extracted implementations.
- Verified entrypoint, adapter, and domain code do not import private modelo application submodules.
- Confirmed `src/aeat/application/modelo/_actions.py` is 258 lines after the extraction wave.
- Confirmed `src/aeat/application/modelo/tests/test_file_flow.py` remains below its legacy budget at 2097 lines after moving justificante metadata seeding into `justificante_metadata.py`.

## Outcome

The modelo application action root is below the hard size budget and remains a facade over focused modules. The public package facade continues to be the consumer boundary.

## Notes

Verification passed for Ruff, compileall, 92 focused application modelo tests, 66 focused import/file/export tests, 36 focused CLI modelo work/export/history tests, 8 architecture-boundary tests, facade smoke imports, and the private-submodule consumer scan. The repository-wide size budget test still fails on unrelated stale git inventory plus overview/config callable offenders, not on modelo production modules.
