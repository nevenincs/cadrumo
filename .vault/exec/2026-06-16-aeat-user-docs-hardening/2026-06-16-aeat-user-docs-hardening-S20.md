---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S20'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden modelo-390.md

## Scope

- `docs/how-to/modelo-390.md`

## Description

- Verify-close: read `modelo-390.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M15 (303->390 dependency had no on-page on-ramp + wrong framing; 303 bindings called `previous_filing` on the page but the CLI reports `relation_prefill`): the page now documents the filed-303-evidence requirement, prepares the same year's Modelo 303 periods first, and names the 303-derived values' binding source correctly.
- Confirm finding M16 (`live iva-wallet pull-history` failed as written): the documented form now carries its required `--from-year`/`--to-year`.

## Outcome

- Page verified compliant at HEAD; findings M15 and M16 resolved (2026-06-19 documentation batch). Delta: none required. CLI conformance gate green.

## Notes

- The 390 honestly documents that its review depends on the same year's periodic 303 values and the establishment paths.
