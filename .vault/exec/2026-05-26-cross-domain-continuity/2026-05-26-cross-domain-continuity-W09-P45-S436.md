---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S436'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Make cross-period verification translation kwargs statically provable to the placeholder-parity gate without weakening validation, then prove the three live localized findings and parity gate pass.

## Scope

- `src/aeat/{core/i18n`
- `application/modelo`
- `entrypoints/cli}/ src/aeat/locales/ src/aeat/**/tests/`

## Description

- Traced the three live cross-period verification projections from canonical stored findings to their CLI localization renderer.
- Replaced dynamic regular-expression `groupdict()` splats with explicit keyword arguments at each translation call, preserving the same runtime values.
- Added an encrypted persisted M390 workflow that snapshots canonical findings, renders real dependency-blocking and pre-activity-suppression findings in Catalan across notices, payload, and text lines, then reloads and compares every canonical message and next action.
- Ran the placeholder-parity gate, focused localization rendering coverage, Ruff, and a scoped whitespace check.

## Outcome

- The required static placeholder-parity gate can now verify all three cross-period translation calls.
- Localized display remains a projection boundary: persisted canonical strings do not change after render and reload.
- The encrypted workflow passed 1 test, placeholder parity passed 3 tests, and the focused CLI integration suite passed 10 tests; owned Ruff and whitespace checks passed.

## Notes

- RAG had no matching indexed code section for the renderer, so the executor confirmed the live renderer and canonical finding producers directly before editing.
