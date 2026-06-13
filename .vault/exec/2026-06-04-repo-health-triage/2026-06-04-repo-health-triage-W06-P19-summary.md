---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P19` summary

W06.P19 reduced several targeted complexity hotspots and persisted the remaining
advisory-red ratchet.

- Modified: `justfile`
- Modified: `.vault/audit/2026-06-04-full-repo-health-diagnostics-audit.md`
- Modified: `.vault/audit/2026-06-04-repo-health-triage-code-review-audit.md`
- Modified: `.vault/plan/2026-06-04-repo-health-triage-plan.md`
- Modified: `src/aeat/application/wizard/_commands.py`
- Modified: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/domain/calculations/registry/_formula_initial_values.py`
- Modified: `src/aeat/domain/calculations/registry/_formula_runtime.py`
- Modified: `src/aeat/entrypoints/cli/_ledger.py`
- Created: `.vault/exec/2026-06-04-repo-health-triage/2026-06-04-repo-health-triage-W06-P19-S75.md`
- Created: `.vault/exec/2026-06-04-repo-health-triage/2026-06-04-repo-health-triage-W06-P19-S76.md`
- Created: `.vault/exec/2026-06-04-repo-health-triage/2026-06-04-repo-health-triage-W06-P19-S77.md`
- Created: `.vault/exec/2026-06-04-repo-health-triage/2026-06-04-repo-health-triage-W06-P19-summary.md`

## Description

S71 and S72 split the production and top-level package test complexity lanes.
S73 and S74 reduced wizard and modelo CLI command hotspots. S75 reduced registry
formula initial-value and M210 resolver complexity. S76 reduced ledger review and
rule-apply projection complexity and cleared local `_ledger.py` Ty diagnostics.
S77 persisted the residual complexity ratchet.

The phase does not claim all-green complexity. It records that production
Complexipy still has 24 functions above threshold and the top-level package test
ratchet still has 8 functions above threshold.

## Verification

- `uv run --no-sync ruff check` passed for the touched S75 and S76 code paths.
- `uv run --no-sync ty check` passed for the touched S75 and S76 code paths.
- Focused registry/modelo tests passed with 53 tests for S75.
- Focused ledger bulk-classify and list-filter tests passed with 23 tests for S76.
- `just audit-complexity-production` exits 1 with 24 production functions above
  threshold.
- `just audit-complexity-tests` exits 1 with 8 top-level package test functions
  above threshold.

## Residuals

The next open implementation row is `W06.P20.S78`, normalizing Ruff scope for
root scratch and probe artifacts. Complexity follow-up remains needed for the
registry binding/record-design hotspots, config Google sync, live error
classification, and the top-level inventory-test collectors.
