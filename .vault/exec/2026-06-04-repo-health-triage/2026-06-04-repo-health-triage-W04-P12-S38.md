---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P12.S38'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P12.S38 - Decide formulas runtime optional or stale ownership

Scope: resolve the `formulas` dependency ownership finding without changing dependency resolution while unrelated `pyproject.toml` and `uv.lock` documentation dependency work is present in the shared worktree.

## Description

- Verified that no production Python module imports the external `formulas` package directly.
- Preserved the runtime dependency because `pyproject.toml` already declares it as the workbook parity evaluator used by the schema-to-sheet parity oracle.
- Added an explicit Deptry `DEP002` ownership exception for `formulas`.
- Updated the dependency comments to state that workbook parity owns `formulas`, not the production registry formula runtime.

## Outcome

- `formulas` is classified as an intentional workbook-parity dependency, not stale registry runtime code.
- No lockfile update was required because the dependency set did not change.
- The remaining Deptry findings for `rich`, `torch`, `playwright-stealth`, and `prompt-toolkit` stay open under W04.P12.S39-S42.

## Verification

- `rg -n "(^|\s)(import formulas|from formulas\b)" src scripts docs pyproject.toml -g "*.py"`
- `uv run --no-sync deptry .`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-06-04-repo-health-triage-plan.md W04.P12.S38`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- `uv run --no-sync deptry .` remains red because later planned rows still own the unresolved dependency findings.
- The shared worktree already contained unrelated Sphinx dependency edits in `pyproject.toml` and matching lockfile changes before this slice; those edits were not included in the S38 commit.
