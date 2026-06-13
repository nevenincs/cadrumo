---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P12.S39'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P12.S39 - Decide rich runtime optional or stale ownership

Scope: resolve the `rich` dependency ownership finding without changing dependency resolution while unrelated documentation dependency edits remain in the shared worktree.

## Description

- Verified that application Python code does not import the external `rich` package directly.
- Verified that Typer declares `rich` as a runtime requirement for its console rendering surface.
- Preserved the direct `rich` pin as the CLI rendering version bound.
- Added an explicit Deptry `DEP002` ownership exception for `rich`.

## Outcome

- `rich` is classified as a direct Typer console-rendering pin, not application runtime code.
- Application code remains import-free for `rich`.
- No lockfile update was required because the dependency set did not change.
- The remaining Deptry findings for `torch`, `playwright-stealth`, and `prompt-toolkit` stay open under W04.P12.S40-S42.

## Verification

- `rg -n "(^|\s)(import rich|from rich\b)" src scripts docs pyproject.toml -g "*.py"`
- `uv run --no-sync python -c "import importlib.metadata as m; print(m.metadata('typer').get_all('Requires-Dist'))"`
- `uv run --no-sync python -c "from typer.main import get_command; from aeat.entrypoints.cli import app; cmd=get_command(app); print(cmd.name); print(len(cmd.commands) if hasattr(cmd, 'commands') else 'no-commands')"`
- `uv run --no-sync deptry .`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-06-04-repo-health-triage-plan.md W04.P12.S39`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- `uv run --no-sync deptry .` remains red because later planned rows still own the unresolved dependency findings.
- The shared worktree still contains unrelated Sphinx dependency edits in `pyproject.toml` and matching lockfile changes; those edits were not included in the S39 commit.
