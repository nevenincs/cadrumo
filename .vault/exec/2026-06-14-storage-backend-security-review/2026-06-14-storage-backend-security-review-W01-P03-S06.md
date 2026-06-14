---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S06'
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
     The S06 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries and ## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key.py`

## Description

- Delete the dead `_write_bytes_secure` static method (no production caller; the
  live primitive is `_write_bytes_secure_fd` in `_materialisation.py`).
- Remove its two `os.open` / `os.write` sensitive-persistence-policy allowlist
  entries.

## Outcome

Dead non-atomic write surface removed; policy gate green. Committed in `e6f280e68`.

## Notes

DEFERRED (owner-gated): the write-only standalone `salt` artefact removal was
split out to `W01.P03.S32`. The `salt` file is redundant for KEK derivation (the
real salt is `master.kdf.salt_b64`) but is load-bearing for the 3-artefact
torn-install detection tuple and is asserted by `test_explicit_provision_mints_and_persists`.
Per the `no-legacy-compatibility` key-management caution, key-store-adjacent
deletions are owner-gated, not autonomous.
