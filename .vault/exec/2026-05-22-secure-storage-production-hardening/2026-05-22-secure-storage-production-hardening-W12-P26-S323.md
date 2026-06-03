---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S323'
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

# W12.P26.S323 registry export parser

## Scope

- `src/aeat/domain/calculations/registry/_export_parse.py`

## Description

- Audited `domain.calculations.registry._export_parse` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module parses operator-supplied AEAT export payloads (BOE-formatted bytes) through registry layout definitions; the parse path is inherently plaintext-input by design (operator hands over a filed declaration artefact for reconciliation).
- Confirmed the XML parse route uses `defusedxml.ElementTree` (entity-expansion and external-DTD attacks mitigated); the byte-stream parser uses the `LATIN_1_ENCODING` core constant; no inline secrets, no per-bucket persistence, no plaintext write surface.
- The `plain-file` signal is appropriately classified as a `plaintext-exception` target: the operator-supplied artefact must be readable as plaintext to be parsed; the parsed records are then handed to the registry validation + secure-storage layers, never round-tripped to disk as plaintext.

## Outcome

- AFR-221 closed: the export parser is a justified plaintext-exception (operator-supplied artefact parse); no source change required.
- No new tests authored — the existing registry export-parse tests cover the layout-driven parse contract.

## Notes

- Audit-only Step; the source file is unchanged.
