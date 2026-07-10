---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S04'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-07-09-m210-irnr-phase-2-engine-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m210-irnr-phase-2-engine with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-05-27-m210-irnr-phase-2-engine-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority and ## Scope

- `src/aeat/domain/period.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority

## Scope

- `src/aeat/domain/period.py`

## Description

- Verify-closed: the M210 agrupacion-anual period token `0A` is ALREADY present and wired at HEAD; no code edit was required or made.

## Outcome

- `0A` is `StandardPeriodCode.ANNUAL` in the canonical grammar (`core/_period.py`), fully resolved through the single `Period.contains` boundary authority (span 1 January-31 December), and covered by an existing helper test (`domain/tests/test_period.py`, `0A` -> 1 Jan-31 Dec). It is a SHARED annual token already used by ~10 modelos (M100, M156, M121, M189, ...), not M210-specific.
- No edit: scoping a shared token to a single modelo in the core grammar would be wrong (it would break the other annual modelos). Per-modelo period applicability is a registry `period_selector` concern, not a core-grammar edit.

## Notes

- The plan step's original scope (`src/aeat/domain/period.py`) named the boundary-helper module; the canonical grammar authority is `aeat.core.Period`. Both already carry `0A`. S04 is satisfied at HEAD with no change.
