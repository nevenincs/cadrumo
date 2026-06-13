---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 7 — aeat sync CLI subcommands

- `src/aeat/entrypoints/cli/sync/` — new typer sub-app with four subcommands:
  `run`, `list-divergences`, `show-divergence`, `resolve-divergence`.
  `run` currently reports the missing in-flight dependencies and
  exits 2 until #8/#17/#9/#25/#21 land; list/show/resolve are fully
  functional against `JsonFileDivergenceRepository`.
- Wired into the root typer app in `src/aeat/entrypoints/cli/__init__.py`.
- `test_cli.py` — `typer.testing.CliRunner` exercises every subcommand
  against a tmp repository, including approve + reject transitions
  and the `--state` filter.

60 unit tests green.
