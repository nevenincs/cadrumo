---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S13'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Extend the period-gate allowlist for the landed docs sequences WorkUnit display frames per the established narrow-rule precedent

## Scope

- `src/cadrumo/core/tests/test_period_combined_string_gate.py`

## Description

- Confirmed `docs/_sequences` and the gate test file carried no
  uncommitted diff before editing (`git status`); the docs-cli-sequences
  campaign's fixture landings (19:02-19:07) were fully committed, and
  the only untracked path was `workstation-setup/`, correctly out of
  scope per the assignment.
- Ran the gate at HEAD (`-n 0`): 26 unallowlisted findings across 13
  docs-sequence JSON fixtures.
- Classified every finding into one of three legitimate, already-
  established shapes (none were a genuine period-input grammar
  regression):
  - The S05 `WorkUnit.name` JSON-string display field
    (`"name": "303-2026-1T"`) — the majority, across
    `file-at-aeat-chain.json`, `filing-spine-chain.json`,
    `filing-spine-visible-target.json`, `filing-spine-work-list.json`,
    `irpf-lifecycle-q1.json`, `iva-lifecycle-q1.json`,
    `modelo-130-inspect-boxes.json`, `modelo-130-review-chain.json`,
    `modelo-303-inspect-boxes.json`, `modelo-303-revision.json`,
    `modelo-349-export.json`, `modelo-349-inspect.json`,
    `verification-reports-work-history.json`. Extended the existing
    consolidated S05 allowlist rule with these 13 files.
  - A NEW variant of the same `WorkUnit.name` field, this time embedded
    inside a captured tab-separated `modelo.work.create` CLI text-output
    blob (`"text": "...\nname\t303-2026-1T\n..."`) rather than a JSON
    `"name"` key — `quickstart-revision.json` and the three
    `review-values-*.json` files. Added a companion narrow rule scoped
    to exactly these 4 files, restricted to the `name\t<modelo>-<year>-
    <period>` text shape (not a bare pattern-name-only exemption).
  - The canonical `modelo-<id>-<year>-<period>.boe` fichero-BOE export
    filename schema (ADR ruling R4), in `iva-lifecycle-q1.json`'s
    `modelo.export --output ./modelo-303-2026-1T.boe` argv and its
    envelope's `output_path` field. Added a narrow rule scoped to that
    one file, restricted to lines containing `.boe`.
- Re-ran the gate: green.
- Ran ruff check + format on the touched file; clean.

## Outcome

Landed in commit `96dc4701b5`. `test_repo_has_no_unallowlisted_combined_period_strings`
passes at HEAD. No pattern loosening: every new allowlist entry stays
path-scoped to the specific landed fixture files and restricted to the
single `"year-qualified quarterly token"` pattern name, with a `text`
filter narrowing the two new companion rules to their exact shape.

## Notes

No incidents. All 26 findings were the two already-recognised display-
frame classes (WorkUnit.name, whether as a JSON field or embedded in a
captured CLI text blob) plus the one already-recognised export-filename
class; none required a fixture-content fix.
