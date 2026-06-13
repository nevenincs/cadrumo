---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P12.S42'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P12.S42 - Declare or optionalize prompt-toolkit consistently

Scope: declare the wizard runtime's direct `prompt_toolkit` imports without mixing unrelated documentation dependency edits into the commit.

## Description

- Verified that wizard production code imports `prompt_toolkit` directly for console validation and typed input/output support.
- Verified that `questionary` depends on `prompt_toolkit>=2,<4`, but the application direct imports still require a direct project declaration.
- Added `prompt-toolkit>=3.0,<4` to runtime dependencies beside `questionary`.
- Regenerated lock metadata from a clean `HEAD` export with only the prompt-toolkit declaration applied.

## Outcome

- `prompt-toolkit` is now declared where the wizard runtime imports it.
- The W04.P12 dependency hygiene rows S38-S42 have all closed their originally identified dependency findings.
- Remaining Deptry output is broader transitive scan noise outside this phase's six finding set.

## Verification

- `uv lock`
- clean-export `uv lock --project <temp>`
- `uv run --no-sync pytest src/aeat/application/wizard/test_dependency_import.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync deptry .`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-06-04-repo-health-triage-plan.md W04.P12.S42`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- `uv run --no-sync deptry .` remains red because broader transitive scan noise remains outside W04.P12.
- The shared worktree still contains unrelated Sphinx dependency edits in `pyproject.toml` and matching lockfile changes; those edits were excluded from the staged clean S42 blobs.
