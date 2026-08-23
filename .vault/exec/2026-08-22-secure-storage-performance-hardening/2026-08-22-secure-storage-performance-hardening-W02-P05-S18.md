---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:c8edfd0a4642afb4c238037d8d4a850f54a38d78aa6cce7935559ac456d1ba39'
step_id: 'S18'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Replace the eager workflow facade with an explicit PEP 562 lazy export map preserving public symbols and direction and ## Scope

- `src/cadrumo/application/workflow/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the eager workflow facade with an explicit PEP 562 lazy export map preserving public symbols and direction

## Scope

- `src/cadrumo/application/workflow/__init__.py`

## Description

- Replace eager workflow facade imports with an explicit closed PEP 562 export map.
- Preserve all 94 canonical public names, cache first resolution, and expose supported
  names through `__dir__` without importing owner modules.
- Add fresh-process import and canonical-owner identity parity gates.

## Outcome

Cold import of the workflow facade loads zero workflow-owned submodules. Every public
name resolves from its declared canonical owner with stable identity and caching. Three
focused tests and Ruff pass; independent review found no blocking issue.

## Notes

No compatibility alias or fallback was added, and no harness or external-client file was
modified.
