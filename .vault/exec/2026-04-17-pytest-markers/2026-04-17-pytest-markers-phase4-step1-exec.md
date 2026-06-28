---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-4 step-1

## rewrite-test-recipes

Rewrote the `justfile` test block:

- `test` unchanged in body (`uv run pytest`); comment updated to `"Run the pytest suite (unit-only by default via pyproject addopts)."`.
- `test-live` now runs `uv run pytest -m "unit or live_read"`.
- `test-live-read` (new) runs `uv run pytest -m "live_read"`.
- `test-domain DOMAIN` (new) runs `uv run pytest -m "unit and domain_{{DOMAIN}}"`.
- `test-live-write` (new, documentation surface) prints a multi-line warning citing charter #116 R1 and then invokes `uv run pytest -m live_write`. Under default env this collects zero items.

All recipes respect the existing `set windows-shell` configuration; the `test-live-write` recipe ships both unix and windows variants for the preceding `echo`/`Write-Host` warning header.

Files touched: `justfile`.

## verification

- `just test` -> green unit run.
- `just test-live-read` -> collects 24 live_read items when gated by env.
- `just test-live-write` -> prints warning, collects zero items under default env.
