---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S04'
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
     The S04 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path and ## Scope

- `src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path

## Scope

- `src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py`

## Description

- Collapse the bbox and non-bbox branches in
  `_observed_casillas_from_declaration_pdf` to one `parse_declaracion_bytes` call.
- Delete `_temporary_sensitive_pdf_path` and `_write_all_fd` plus their re-exports
  in `_declarations.py`, the test support module, and the direct unit test.
- Remove the now-stale `tempfile.mkstemp` / `os.write` entries from the
  sensitive-persistence-policy allowlist so the gate proves the disk path is gone.

## Outcome

No decrypted declaration bytes touch disk on any extraction branch. The
sensitive-persistence-policy gate passes with the allowlist entries removed
(245 passed across the declaracion + sede + policy suites); collect-only clean
across the touched trees. Committed in `25224b9e0`.

## Notes

Blast radius beyond the two scope files: the facade re-export, the test-support
re-export, the obsolete direct unit test, and the policy allowlist. All swept in
the same commit.
