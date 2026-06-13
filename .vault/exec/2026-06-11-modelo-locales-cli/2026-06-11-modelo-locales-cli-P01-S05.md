---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S05'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P01.S05 expose coverage and drift records

Scope: `src/aeat/locales/_modelo_manager.py`.

## Description

- Add missing and stale drift detection for schema-local locale TOML leaves.
- Add coverage summaries for one modelo revision and locale.
- Compare missing leaves against the selected revision while checking modelo-wide stale continuity leaves against the whole modelo.
- Load inventory from registry manifest and revision data without applying locale TOML, so stale locale keys can be reported instead of aborting audit.

## Outcome

The manager can now report per-locale, per-modelo, per-revision translation coverage and drift. This is the data contract needed by the upcoming `aeat.locales modelo audit`, `scaffold --check`, and `coverage` commands.

## Notes

Focused verification passed for committed M130 full coverage, committed M303 inventory, synthetic continuity-key coverage, and synthetic stale/missing drift detection. Existing M100 and M200 registry loader validation failures remain outside this locale-manager slice.
