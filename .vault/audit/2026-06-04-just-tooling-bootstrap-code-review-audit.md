---
tags:
  - '#audit'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-just-tooling-bootstrap-research]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
  - '[[2026-06-04-just-tooling-bootstrap-plan]]'
---

# `just-tooling-bootstrap` Code Review

## JUST-001 | LOW | Full shared virtual environment sync still needs a clean window

The manifest and lockfile are consistent, but the current shared `.venv` could not complete `uv sync --no-install-project` because an existing `vaultspec-rag.exe` process lock prevented replacement of that executable. A minimal no-deps repair restored `vaultspec-core`, `deptry`, and `vulture` spawning for this task, but a clean full sync still requires the locking process to release `vaultspec-rag.exe`. This is an environment state issue, not a lockfile defect.

## JUST-002 | INFO | Security audit fallback may download Semgrep on first use

`audit-security` now prefers a PATH `semgrep` executable and falls back to `uvx --from semgrep semgrep`. The fallback resolves successfully, but the first run on a fresh workstation may require network access to populate the `uvx` cache.

## JUST-003 | INFO | Advisory audits intentionally expose existing debt

`quality-audit` uses error-tolerant recipe calls because full-tree type, complexity, dead-code, dependency, duplication, and security discovery can report existing project debt. The strict `quality` lane remains separate and composes the existing daily hard gates. Final verification confirmed this behavior: `audit-deps` reports 6 existing production dependency issues, `audit-dead-code` reports production dead-code candidates, and `audit-duplication` reports 22 clone groups.
