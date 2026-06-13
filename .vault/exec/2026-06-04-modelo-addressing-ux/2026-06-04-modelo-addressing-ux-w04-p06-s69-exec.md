---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S69'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S69` quickstart natural-key lifecycle rewrite

Step scope: `docs/how-to/quickstart.md`.

## Description

- Validate that the quickstart lifecycle path uses modelo, year, and period addressing.
- Confirm the quickstart no longer asks the reader to pass work-unit or calculation-revision IDs between commands.
- Preserve the exact-ID path as an advanced automation or ambiguity-resolution escape hatch.
- Verify educational-doc command and link conformance against the live CLI.

## Outcome

The quickstart now shows create, calculate, verify, and export commands addressed by `--modelo 130 --year 2024 --period 1T`. Exact IDs are mentioned only as advanced inputs for automation or explicit ambiguity resolution.

Verification passed with `uv run pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

No additional source edit was needed during this step beyond persisting the already natural-key quickstart state and recording verification. The docs conformance test emitted existing Click deprecation warnings only.
