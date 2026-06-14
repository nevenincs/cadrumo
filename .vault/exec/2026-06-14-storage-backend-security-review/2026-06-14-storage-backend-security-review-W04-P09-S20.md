---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S20'
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
     The S20 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Implement the manifest-digest cross-check over a timestamp-independent projection or correct the contract docstring and ## Scope

- `src/aeat/application/bucket_maintenance/_manifest_digest.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the manifest-digest cross-check over a timestamp-independent projection or correct the contract docstring

## Scope

- `src/aeat/application/bucket_maintenance/_manifest_digest.py`

## Description

- Correct the `_manifest_digest` module and function docstrings: they claimed the
  importer recomputes-and-compares the digest, which it does not and cannot (the
  manifest carries host-specific lifecycle timestamps). Document the true
  mechanism: the digest is bound into the sealed payload AEAD associated data, so
  a tampered digest fails the authentication tag and the import is refused at
  decryption.

## Outcome

Doc-vs-code contract gap closed (flagged by both the crypto and cross-machine
axes). 4 manifest-digest tests green. Committed in `ea1baea5e`.

## Notes

A literal recompute cross-check would require a timestamp-independent manifest
projection; the AEAD binding already provides authoritative integrity, so the
docstring correction is the right resolution rather than adding a redundant gate.
