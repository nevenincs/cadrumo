---
tags:
  - "#exec"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please phase-2 task-1 — justfile release recipes
related:
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-adr]]"
issue: wgergely/aeat#60
---

# exec: release-please phase-2 task-1

## intent

Add `release` and `release-apply` recipes to `justfile` with
`[unix]` + `[windows]` parity, following the project's established
cross-platform recipe pattern.

## actions

- Added a section `── Release (local-only; see RELEASING.md + aeat#60) ──`
  between the Google-Workspace-fixtures block and its predecessor.
- `release` — both OS variants guard on `node` and `gh` availability,
  capture a GitHub token via `gh auth token`, ensure `var/release/`
  exists (already `.gitignore`-covered via the blanket `var/`
  entry), and run
  `npx --yes release-please@16 release-pr --dry-run --debug`
  against `wgergely/aeat` on `main`, teeing the output to
  `var/release/release-please.log`.
- `release-apply` — both OS variants require clean tree on `main`
  and the presence of the dry-run log, then print a numbered
  instruction list for the human operator (update manifest,
  update `pyproject.toml`, update `__init__.py`, update
  `CHANGELOG.md`, stage, commit as `chore(release): vX.Y.Z`, tag as
  `vX.Y.Z`, never push).
- First draft used bash `cat <<'EOF'` / pwsh `@'...'@` here-docs for
  the instruction block; `just --list` refused to parse because
  the unindented heredoc body collided with `just`'s recipe lexer.
  Replaced with indented `echo` / `Write-Host` sequences — the
  project's established pattern for multi-line recipe output.

## verification

- `just --list` shows `release` and `release-apply`.
- `just lint`, `just typecheck`, `just test`, `just hooks` all
  green on Windows.
- `ls .github/workflows/` shows only the pre-existing legacy
  `ci.yml`; **no** `release-please.yml` was introduced.
