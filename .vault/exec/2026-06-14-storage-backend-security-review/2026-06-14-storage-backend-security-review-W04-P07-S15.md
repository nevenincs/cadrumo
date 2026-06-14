---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S15'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model and ## Scope

- `src/aeat/domain/transactions/_raw_transaction.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model

## Scope

- `src/aeat/domain/transactions/_raw_transaction.py`

## Description

- Replace the `_resolve_source_path` validator (which called `.resolve()`) with
  `_basename_source_path`, storing only `value.name`; update the field and
  validator docstrings.

## Outcome

`RawProvenance.source_path` now persists a basename, not a host-specific absolute
path: no directory/username leak in the persisted or exported record, and no
cross-OS `.resolve()` mutation on rehydration. The live import file-read uses its
own path parameter, so file access is unaffected. 164 transaction/import/invoice
tests plus 18 ledger/workflow tests green. Committed in `d7b001fa6`.

## Notes

source_sha256 already carried the content identity, so no information is lost.
