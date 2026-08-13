---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0ceb9b2acb5447886bcf11174e8224de58dd67d74ad257852ed370e8f83e7402'
step_id: 'S20'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Expose the persistence adapter facade without exporting implementation internals and ## Scope

- `src/cadrumo/adapters/persistence/operations/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Expose the persistence adapter facade without exporting implementation internals

## Scope

- `src/cadrumo/adapters/persistence/operations/__init__.py`

## Description

- Re-export `OperationJournalRepository` and `OperationLeaseFilesystemRepository` from the package root.
- Declare the exact two-name public surface through `__all__`.
- Keep `OperationLeaseStorage` adapter-local and prove it is absent from the package namespace.
- Add a direct package-facade test using only the public adapter package.

## Outcome

The persistence facade exposes only the concrete journal and owner-lease repositories. It does not promote the shared lease-storage and lock helper, leaving journal-lock composition internal to the two concrete adapters.

Focused verification passed:

- `pytest`: 32 passed across the S18/S19 regression suite and the new facade contract.
- Ruff check and format check: passed.
- Basedpyright: 0 errors, 0 warnings, 0 notes.
- Path-scoped relative-import gate: passed.

## Notes

Fresh code and vault RAG grounding, whole-file adapter reads, exact-symbol confirmation, and the S18/S19 execution and review records all converge on the two-repository facade. The RAG code index reported one unpublished section; the exact-source sweep supplied the required absence evidence.

This record is scaffolded and the implementation remains open for independent review. The plan step is intentionally unchecked and no commit was created.

