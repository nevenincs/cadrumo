---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P12.S41'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
  - '[[2026-04-12-playwright-anti-bot-adr]]'
---

# W04.P12.S41 - Declare or optionalize playwright-stealth consistently

Scope: correct the `playwright-stealth` dependency placement for the production browser evasion strategy without mixing unrelated documentation dependency edits into the commit.

## Description

- Verified that `PlaywrightStealthEvasion` imports `playwright_stealth` from production browser code.
- Verified that `BrowserSession` defaults to `PlaywrightStealthEvasion`.
- Moved `playwright-stealth` from the dev dependency group to project runtime dependencies beside `playwright`.
- Regenerated lock metadata from a clean `HEAD` export with only the dependency-placement change applied.

## Outcome

- `playwright-stealth` is now declared where the production import uses it.
- The existing browser evasion test still passes against the real installed package.
- The remaining Deptry finding for `prompt-toolkit` stays open under W04.P12.S42.

## Verification

- `uv lock`
- clean-export `uv lock --project <temp>`
- `uv run --no-sync pytest src/aeat/adapters/outbound/aeat/browser/test_evasion.py`
- `uv run --no-sync deptry .`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-06-04-repo-health-triage-plan.md W04.P12.S41`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- `uv run --no-sync deptry .` remains red because later planned rows and broader transitive scan noise are still open.
- Deptry also warned that `src/aeat/application/modelo/__init__.py` has an unrelated syntax error while scanning; this slice did not modify that file.
- The shared worktree still contains unrelated Sphinx dependency edits in `pyproject.toml` and matching lockfile changes; those edits were excluded from the staged clean S41 blobs.
