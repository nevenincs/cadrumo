---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S326'
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

# W12.P26.S326 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Audited `domain.calculations.registry._loader` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module is the TOML authoring-compiler that reads the bundled registry tree under `src/aeat/_data/registry/aeat/`; the `plain-file` signal is by-design (the loader's contract per the `aeat-registry-authority-flow` rule is to read shipped TOML, compile to typed schema, and hand off to the validated authority).
- The loader writes nothing to disk; every output flows into strict pydantic v2 `ModeloDefinition` / `ModeloRevision` instances cached by the registry tree fingerprint.

## Outcome

- AFR-224 closed: justified plaintext exception (TOML authoring-compiler reads bundled registry data). No source change required.

## Notes

- Audit-only Step.
