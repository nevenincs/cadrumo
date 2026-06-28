---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S74'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S74` CLI reference regeneration check

Step scope: `docs/cli`.

## Description

- Locate the project CLI reference generator and drift gate.
- Regenerate the CLI reference through the live command-tree generator.
- Verify committed `docs/cli` pages match freshly generated output.
- Confirm natural-key modelo work, export, and reconcile flags are present in `docs/cli/app.rst`.

## Outcome

The committed CLI reference already matched fresh output from `aeat.entrypoints.cli._doc_reference.generate_cli_reference_in_subprocess`. No `docs/cli` file content changed during regeneration. The generated reference includes the natural-key `--modelo`, `--year`, `--period`, and `--select` options on the updated modelo work, export, and reconcile command surfaces.

Verification passed with `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_doc_reference_drift.py src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.

## Notes

Because the generator reported no drift, this step persists verification evidence and the plan closure only.
