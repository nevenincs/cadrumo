---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:92e5d13d171c7a83646b7305211b8b10cbcf8515ae22bef1382a69757db622f0'
step_id: 'S270'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Retire the six newly orphaned manager action translations from all four production catalogues after the canonical TUI cutover, then rerun locale audit and scaffold drift

## Scope

- `src/cadrumo/locales/ and dev/locales/`

## Description

- Run the production locale audit after the TUI manager cutover.
- Confirm the six reported keys have zero production call sites.
- Retire the orphan entries from all four catalogues with the canonical locale scaffold.
- Rerun scaffold drift and the complete production audit after the flows relocation settles.

## Outcome

The canonical scaffold removed the same six `flows.manager.*` action keys from Catalan, English, Spanish, and Hungarian, for 24 catalogue entries total. Fresh scaffold drift and production audit report `ok` for all four locales with zero missing keys, extra keys, placeholder mismatches, or registry moves.

## Notes

The first post-edit check crossed an unrelated in-progress public `flows` module relocation and failed import of the old `_capability` module. That run is not evidence. After the relocation commit landed, the same canonical check completed cleanly. No locale entry was edited by hand.
