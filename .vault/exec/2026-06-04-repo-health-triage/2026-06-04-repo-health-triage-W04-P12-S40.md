---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P12.S40'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
  - '[[2026-05-30-security-supply-chain-2026-05-30-audit]]'
---

# W04.P12.S40 - Decide torch runtime optional or stale ownership

Scope: remove the stale runtime `torch` dependency and its PyTorch CUDA index/source metadata without mixing unrelated documentation dependency edits into the commit.

## Description

- Verified that application Python code does not import `torch`.
- Reused the supply-chain audit finding that default runtime CUDA PyTorch wheels are not defensible without an owning runtime feature.
- Removed `torch>=2.4` from project runtime dependencies.
- Removed the PyTorch CUDA index/source override and the now-obsolete vaultspec-rag torch-direct-dependency marker.
- Regenerated the lockfile from a clean `HEAD` export with only the torch removal applied, so unrelated documentation dependency WIP stayed out of the S40 commit.

## Outcome

- `torch` is no longer an application runtime dependency.
- The CUDA `download.pytorch.org/whl/cu130` source is no longer configured in `pyproject.toml`.
- Torch can still appear transitively in the lockfile through dev tooling; it is no longer owned by the application dependency set.
- The remaining Deptry findings for `playwright-stealth` and `prompt-toolkit` stay open under W04.P12.S41-S42.

## Verification

- `rg -n "(^|\s)(import torch|from torch\b)|torch\." src scripts docs pyproject.toml -g "*.py" -g "*.toml"`
- `uv lock`
- clean-export `uv lock --project <temp>`
- `uv run --no-sync deptry .`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-06-04-repo-health-triage-plan.md W04.P12.S40`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- `uv run --no-sync deptry .` remains red because later planned rows still own unresolved dependency findings and broader transitive scan noise.
- The shared worktree still contains unrelated Sphinx dependency edits in `pyproject.toml` and matching lockfile changes; those edits were excluded from the staged clean S40 blobs.
