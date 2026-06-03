---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S325'
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

# W12.P26.S325 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_legal.py`

## Description

- Audited `domain.calculations.registry._legal` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module defines typed `LegalReference`, `LegalCatalogue`, and `SourceReference` records consumed by every casilla / formula / revision in the registry to ground regulatory values; the file is pure record schema, no I/O.
- The `plain-file` signal is the read-path artefact of the legal catalogue's TOML provenance under `src/aeat/_data/registry/aeat/legal/`; the actual TOML read happens in the loader (S326) and the parsed records flow through these typed shapes.

## Outcome

- AFR-223 closed: justified plaintext exception (in-memory legal-reference record schema). No source change required.

## Notes

- Audit-only Step.
