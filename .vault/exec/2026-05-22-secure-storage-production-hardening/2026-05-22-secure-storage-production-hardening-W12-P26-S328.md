---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S328'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-production-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# W12.P26.S328 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_record_design.py`

## Description

- Audited `domain.calculations.registry._record_design` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module defines AEAT Diseño de Registros parser shapes used to project filing artefacts onto operator-readable record layouts; pure schema + pure-Python transformers.
- The `plain-file` signal is the read-path artefact of the bundled record-design TOML; the actual TOML read happens in the loader (S326) and the typed records flow through these in-memory shapes.

## Outcome

- AFR-226 closed: justified plaintext exception (in-memory record-design shapes). No source change required.

## Notes

- Audit-only Step.
