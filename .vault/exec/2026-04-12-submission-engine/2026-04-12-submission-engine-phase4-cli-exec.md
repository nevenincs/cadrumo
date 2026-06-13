---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: submission engine — phase-4 CLI + settings
related:
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# phase-4: settings + CLI wiring

## artefacts produced

- `src/aeat/config.py` — four new Settings fields under the
  "Submission engine (#42)" header: `aeat_submissions_dir`,
  `aeat_submission_dry_run_default`,
  `aeat_submission_require_human_confirmation`,
  `aeat_submission_browser_trace_dir`.
- `env/.env.example` — mirror entries for the four new env vars.
- `src/aeat/entrypoints/cli/submission/` — Typer sub-app with five subcommands
  (`preflight`, `dry-run`, `submit`, `show`, `list`) and
  `_helpers.py` containing in-process Protocol stubs and
  `build_engine()`. The `submit` subcommand exits 2 without the
  `--i-understand-this-is-real` flag.
- `src/aeat/entrypoints/cli/__init__.py` — registered `submission_module.app`.

## verification

- `uv run pytest src/aeat/entrypoints/cli/submission -q` — passed.
- `uv run pytest tests/test_config.py -q` — passed.
