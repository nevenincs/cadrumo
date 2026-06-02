---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S289'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
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

# evaluate access_gate __init__.py env-var read pre-Settings bootstrap

## Scope

- `either lift into Settings (preferred) or write an ADR exception note formalising the early-bootstrap-window exception`
- `src/aeat/access_gate/__init__.py`

## Description

Audited `aeat/core/access_gate/__init__.py` env-var reads against
the settings-di migration goal.

## Outcome

Already resolved. The access-gate's AEAT-prefixed env-var read was
lifted into `Settings.aeat_live_tests_enabled` under settings-di
plan Steps P02.S06 and P02.S07. The class now reads
`self.settings.aeat_live_tests_enabled` (line 104 for the
`require_live_read` check; line 169 for the audit-snapshot helper).
The only remaining `os.environ` read is for `PYTEST_CURRENT_TEST`,
which pytest sets automatically per test and is not AEAT
configuration; the inline comment at lines 144-151 documents this
as the single legitimate exception.

The override-seam coverage shipped earlier this session
(commit `1018d024f exec(settings-di): close P02.S08 — override-seam
coverage for live-read gate`) proves the migrated reader observes
`override_settings()` without ever mutating `os.environ`.

## Notes

The plan's path (`src/aeat/access_gate/__init__.py`) is stale; the
canonical home is `src/aeat/core/access_gate/__init__.py`. No
additional code authored by this record.

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
