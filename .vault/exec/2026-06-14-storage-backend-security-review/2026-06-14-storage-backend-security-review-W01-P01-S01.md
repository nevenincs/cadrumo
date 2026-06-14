---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S01'
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
     The S01 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Replace export-archive HKDF sealing-key derivation with Argon2id and persist the kdf params in the recovery-wrap member and ## Scope

- `src/aeat/application/bucket_maintenance/_service.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace export-archive HKDF sealing-key derivation with Argon2id and persist the kdf params in the recovery-wrap member

## Scope

- `src/aeat/application/bucket_maintenance/_service.py`

## Description

- Replace the HKDF recovery-wrap sealing-key derivation with Argon2id
  (`derive_kek_with_params` at the OWASP baseline) over a fresh per-archive salt,
  on both the export and import paths.
- Rewrite the recovery-wrap member to record `{kdf: argon2id, salt_b64,
  memory_cost, time_cost, parallelism}`; `_recovery_wrap_kdf` reads and validates
  them (non-positive refused). Promote `derive_kek_with_params` + the Argon2
  constants to the master_key package surface.

## Outcome

An exported recovery-passphrase archive is no longer offline-brute-forceable: the
sealing key now costs a full Argon2id derivation per guess. Per no-legacy the
prior hkdf-sha256 format is deleted. 80 bucket_maintenance + master_key tests
green. Committed in `d8abf5673`. Unblocked once the peer tree-sweep cleared the
prior WIP on `_service.py`.

## Notes

A wrong-passphrase or tampered-low-cost member self-defeats (derives a different
KEK that cannot decrypt the AEAD payload) in addition to the explicit refusals.
