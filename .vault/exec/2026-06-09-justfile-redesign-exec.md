---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S45'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# command output hardening (S21-S45)

## Description

- Audited every check-, audit-, test-, env-doctor, and docs-check recipe for output cognitive load and readability; the principle applied throughout is that passing/green results are not reported (silent or a single aggregate line) and only actionable findings reach the developer.
- Restored ty into the type gate alongside pyright through a signal-only wrapper `scripts/check_types.py`; silent on success, compact rule/file-grouped summary on failure, with `audit-types` as the uncapped escape hatch.
- Added a reusable quiet-on-success primitive `scripts/quiet_ok.py` and routed check-style, check-format, check-imports, check-dependencies, and check-pre-commit through it so each is silent on success and replays full output only on failure.
- Replaced the fail-fast check-all chain with a consolidated dashboard `scripts/check_all.py` that runs every fast gate to completion and reports only failing gates; dropped check-pre-commit from the set to remove a redundant second ruff and ty pass.
- Redesigned `scripts/audit_complexity.py` to lead with a one-line aggregate and show only the worst-ranked cyclomatic, maintainability, and cognitive findings (capped, remainder counted): output fell from 481 lines to 57.
- Added `scripts/filter_jscpd.py` and piped audit-duplication through it to strip ANSI, drop the summary box-table and timing, and present a one-line aggregate plus a capped clone list.
- Added `--quiet` to the semgrep invocations in check-security; added section headers to audit-debt-dashboard.
- Reduced pytest progress verbosity (`-q` to cancel the global `-v`) on test-unit, test-integration, test-live, test-coverage, and the docs-check pytest pass; test-smoke keeps `-v` deliberately.
- Suppressed just command-echo on the check-/fix-/audit- family by prefixing recipe lines with `@`.
- Added autofix recipes fix-imports and fix-all alongside the existing fix-style and fix-format.
- Swept stale recipe references in `scripts/check_relative_imports.py` and `pyproject.toml` to the new taxonomy.

## Outcome

- ty is back in the type gate (ADR §1 satisfied) and emits actionable signal instead of a 25k-line dump.
- Fast gates are silent on success; the named offender audit-complexity and audit-duplication now lead with aggregates and cap their detail.
- All 45 plan steps are checked; the justfile parses and the fast gates were exercised.

## Notes

- The actual type, lint, complexity, and duplication findings these commands surface are real codebase debt and are explicitly out of scope for this harness pass; they are surfaced cleanly for a later remediation campaign.
- check-types remains a non-zero (red) gate until that debt is addressed; this is correct gate behaviour, not a regression.
