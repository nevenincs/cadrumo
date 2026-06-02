---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
step_id: 'S02'
related:
  - "[[2026-05-28-schema-hardening-continuity-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Add generic retirement and unmatched-continuity validation semantics

## Scope

- `src/aeat/domain/calculations/registry/_validate_cross_revision.py`

## Description

Audited current state of
`src/aeat/domain/calculations/registry/_validate_cross_revision.py`
against the plan's P02.S02 brief.

## Outcome

Already implemented. The validator file (424 lines) already carries
the generic retirement and unmatched-continuity semantics required
by the Step:

- `_validate_strict_retired_continuity_surfaces` — requires explicit
  `evolution_kind = "retired"` declarations when a strict continuity
  chain disappears between revisions.
- `_format_unmatched_continuity_evolution_failure` — formats the
  refusal for unmatched-continuity evolution attempts (source
  continuity id missing, or target revision still declares the
  retired id).
- Per-modelo iteration honouring `continuidad_validation = "strict"`
  on either side of the revision pair.

The work landed under an earlier session and was already
production-active; only the plan-checkbox close and the exec record
were outstanding. Closure is structural documentation of completed
implementation.

## Notes

No code changes authored by this record — the implementation
predates the P02 carve-out. Validator behaviour is covered by the
P02.S03 real-behavior tests audited in the sibling step record.
