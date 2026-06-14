---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S26'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C1-1a Redirect the two named sha256-hex helper redeclarations to core.hashing.sha256_hex and ## Scope

- `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C1-1a Redirect the two named sha256-hex helper redeclarations to core.hashing.sha256_hex

## Scope

- `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py`

## Description

- Re-verified at HEAD: `sql/_secure_object_crypto.sha256_hex` (a byte-identical
  same-name re-declaration) and `calc_sheets/_workbook_export._sha256`.
- `_secure_object_crypto` now imports `sha256_hex` from core for its
  `derive_revision_id` use; `secure_objects.py` imports `sha256_hex` from core
  directly (rather than re-exporting through `_secure_object_crypto`).
- `_workbook_export` consumes `sha256_hex` at both call sites; dropped the local
  `_sha256` def and the unused `hashlib` import.

## Outcome

Committed as `c94f0c4dd`, tagged `relocation:sha256_hex`. Ruff clean; 242
storage/calc_sheets tests green incl. secure-object roundtrips and revision-id
derivation. No public shape change.

## Notes

Routed the `secure_objects` consumer to core directly to avoid leaving a
re-export shim in `_secure_object_crypto`.
