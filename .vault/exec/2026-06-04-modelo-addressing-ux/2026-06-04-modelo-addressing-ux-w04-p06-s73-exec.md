---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S73'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S73` Filing spine pointer and selector explanation

Step scope: `docs/how-to/filing-spine.md`.

## Description

- Explain the visible filing target used by the common CLI workflow.
- Document registry-revision conflict refusal without making raw IDs the normal path.
- Clarify that one work unit owns the active filing workspace and current pointers.
- Document calculation revision multiplicity, selector names, and command-specific defaults.
- Verify educational-doc command and link conformance against the live docs test lane.

## Outcome

The filing-spine guide now describes the operator-facing filing address as active profile, modelo, filing year, and period, with registry revision resolved internally and ambiguity refused. It explains the singleton work-unit workspace, current calculation, filed calculation, and current filing pointers, and names the supported revision selectors: `current`, `latest-draft`, `latest-verified`, `filed`, and explicit calculation-revision ID.

Verification passed with `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

The raw-ID scan for `docs/how-to/filing-spine.md` returned no matches after replacing copy/paste wording with neutral exact-addressing guidance.
