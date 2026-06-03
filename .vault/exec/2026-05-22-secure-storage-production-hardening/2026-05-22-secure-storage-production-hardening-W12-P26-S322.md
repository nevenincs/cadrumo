---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S322'
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

# W12.P26.S322 registry bindings

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`

## Description

- Audited `domain.calculations.registry._bindings` against the target `remote-mirror` (owner `W12.P24.S98`).
- Confirmed the module defines typed `DataBindingDefinition` records and binding-selector / per-source binding-resolver shapes; the file does no I/O, opens no network connection, and reads no plaintext file.
- The `remote-provider` signal refers to the binding-selector enumeration covering `borrador`, `censo`, `notifications`, `expedientes`, and `iva-remote-state` data sources that are consumed via local captured snapshots (per the `aeat-safety-legal-gates` charter — live AEAT writes are forbidden; reads go through captured-snapshot mirrors).
- Confirmed the binding records carry no remote-fetch handle; they reference snapshot ids by content-address, and the actual snapshot reads happen via the `SecureSnapshotRepository` family in `application.live` already validated by the W12.P26.S319/S321 pair.

## Outcome

- AFR-220 closed: the remote-provider bindings reference captured-snapshot mirrors, not live remote reads; the `remote-mirror` target is appropriately satisfied. No source change required.
- No new tests authored — the existing registry binding contract tests cover the shape and the snapshot consumers test the read path.

## Notes

- Audit-only Step; the source file is unchanged.
