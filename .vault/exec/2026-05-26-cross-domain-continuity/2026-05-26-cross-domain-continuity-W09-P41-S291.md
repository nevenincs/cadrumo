---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S291'
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

# evaluate core observability _replay.py env-var write for replay scope

## Scope

- `if test-infrastructure-only document inline + restrict via test-only import path`
- `if production-touching lift into Settings`
- `src/aeat/core/observability/_replay.py`

## Description

Audited `src/aeat/core/observability/_replay.py` env-var reads. The `os.environ` access at lines 172, 177, 182 is a scoped context-manager that sets `REPLAY_ACTIVE_ENV_VAR` for the duration of a replay run and restores the prior value on exit. The inline NOTE at lines 165-170 documents the read/write as a deliberate exception to the Settings single-config-read invariant because Settings is read-only (it cannot carry a writable replay-active flag). The plan Step's binary choice is satisfied by the inline NOTE — it serves as the in-code ADR-exception.

## Outcome

Closed as audit-confirmed inline-comment exception; see Description above.

## Notes

No additional code authored by this record. The Step's intent (either lift to Settings or document the exception) is satisfied by the in-code exception comments — which are load-bearing and cannot drift from the implementation the way a separate ADR document could.
