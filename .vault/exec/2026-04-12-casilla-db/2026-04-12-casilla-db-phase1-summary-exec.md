---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 summary

Implemented the casilla catalogue feature on a new `aeat.domain.casillas` package,
added canonical corpus files for `MODELO_130`, `MODELO_303`, and `MODELO_390`,
wired the `aeat casillas` CLI, and documented the contributor workflow for
adding new catalogues.

- Created: `src/aeat/domain/casillas/**`
- Created: `corpus/casillas/**`
- Created: `docs/casillas.md`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/config.py`
- Modified: `env/.env.example`
- Created: `.vault/audit/2026-04-12-casilla-db-review.md`

## Description

The implementation follows the issue-23 coordination rule by avoiding
`src/aeat/domain/schema/` and instead establishing a dedicated `src/aeat/domain/casillas/`
subpackage. Canonical persistence is strict and verified, the CLI surface is
present, and the branch now carries the required research, ADR, plan, exec, and
audit artefacts.

## Tests

`just lint`, `just typecheck`, `just test`, and `just hooks` all passed on the
final tree. `uv run aeat casillas verify` also passed for the three checked-in
catalogues.
