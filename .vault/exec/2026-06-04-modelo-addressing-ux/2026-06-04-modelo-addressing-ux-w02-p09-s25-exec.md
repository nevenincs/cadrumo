---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:c7e17c760c1ce68fbc85e855875f934c260b831a0933461674274ea420470614'
step_id: 'S25'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P09.S25 visible-target revision conflict coverage

Scope:
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Cover `modelo work create` refusing a different requested registry revision for an already-active visible filing target.
- Assert the diagnostic names the existing and requested revisions.
- Assert no second active work unit appears in `work list`.

## Outcome

The CLI now has regression coverage for the no-second-active-work-unit rule on visible filing targets.

## Notes

- Focused natural-key workflow tests passed.
