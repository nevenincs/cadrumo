---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S81'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P20.S81 Semgrep Security Policy Burn-Down

Scope: `.semgrepignore`, Semgrep production-security lane, and production
source files reported by the lane.

## Description

- Re-run `just audit-security` and enumerate all current blocking findings.
- Preserve the source-class split in `.semgrepignore` for mirrored data, tests,
  and test-support code.
- Fix or precisely justify each production-source finding instead of excluding
  production files from Semgrep.
- Add parser and CLI dynamic-import allowlists where registry or CLI data drives
  import resolution.

## Outcome

`just audit-security` now reports 0 findings and 0 blocking findings. The scan
still targets 988 tracked files under `src/aeat`, runs 323 rules from the stock
Semgrep auto configuration, and skips mirrored data and test surfaces through
the existing `.semgrepignore` source-class policy.

Scoped verification also passed Ruff, Ty, and focused FX/registry tests for the
touched files.

## Notes

The Python 3.7 compatibility findings were false positives for this project
because `pyproject.toml` requires Python `>=3.13`; those imports now carry exact
line-level Semgrep rationale. Controlled SQL bootstrap, private POSIX directory
mode, the exact ECB refresh URL, cross-domain registry registration imports,
registry parser imports, and CLI lazy imports are likewise documented at the
audited line instead of hidden through `.semgrepignore`.
