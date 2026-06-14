---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S07'
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
     The S07 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Bind namespace and object-key digest and schema version into the secure-object payload AEAD associated data and ## Scope

- `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Bind namespace and object-key digest and schema version into the secure-object payload AEAD associated data

## Scope

- `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`

## Description

H3 (the at-rest integrity centerpiece) was attempted and DEFERRED as too large to
land safely without a dedicated, full-suite-validated pass. This record captures
the technical plan so the next focused session executes it cleanly.

## Outcome

STEP OPEN. Findings from the attempt:

- The secure-object `payload` column is an `EncryptedBytes` SQLAlchemy
  TypeDecorator that auto-encrypts with a static column-type AAD
  (`aeat.column.encrypted_bytes.v1`). The decorator's `process_bind_param(value,
  dialect)` signature cannot see the row's `namespace`/`object_key`, so binding
  row identity into the AEAD AAD (S07) REQUIRES moving payload encryption out of
  the decorator into explicit repository encryption at `_save_internal_in_session`
  (the single write site, `secure_objects.py:~891/916`), and explicit decryption
  at every read site. Read sites: `iter_records_with_failures` (raw `text()`
  select + `decrypt_encrypted_bytes_column`, the hot list/iter path), `load` ->
  `_record_from_row` (ORM auto-decrypt via the decorator), the
  `previous_metadata.payload` read in `_save_internal_in_session` (used for the
  prior-hash fallback), and `_secure_object_integrity.py`. Missing any read site
  silently returns ciphertext as plaintext, so the column switch must be exhaustive.

- `payload_hash = sha256_hex(plaintext)` is written at `_write_revision_metadata`
  (`:988`), so read-time verification (S08) is `sha256_hex(decrypted) ==
  payload_hash`. `load` and the iterator are the two read paths to gate.

- TEST RECONCILIATION REQUIRED (the S08 attempt failed these 7 because they
  deliberately corrupt the stored payload to exercise DOWNSTREAM failure modes,
  and the stronger check correctly intercepts earlier):
  `test_secure_bound_repository_contract::test_dummy_repository_satisfies_secure_contract`;
  `test_attachment_store_roundtrip::test_attachment_manifest_id_sha_mismatch_surfaces_at_load`;
  the two `..._envelope_metadata_drift_fails_closed[...]` cases; the three
  `..._malformed_attachment_manifest_payload_is_localized_for_all_read_paths[...]`
  cases. Each must be updated to expect the hash-mismatch refusal, or restructured
  to corrupt in a way that tests its intended downstream path.

- APPROACH OPTIONS: (A) move payload encryption to explicit + bind
  `namespace||object_key_digest||schema_version` into the AAD (cleanest crypto;
  highest blast radius). (B) additive keyed-MAC column (`HMAC(DEK-subkey,
  namespace||object_key||schema_version||payload_hash||revision_id)`) verified on
  read (lower blast radius; adds a column; per no-legacy, dev buckets re-provision).
  Either closes the row-substitution gap; B is lower-risk to land incrementally.

## Notes

A peer's bulk "clear the tree" commit (`f3a4caf3e`) swept the WIP S08 attempt into
HEAD with the 7 failing tests; commit `eece62072` restored the read path. Land H3
on a clean branch slice with the full storage suite (not just `bucket/tests/`) as
the gate. Also fixed a latent W03.P06 regression in the same restore: the
production-file-write inventory entry for `write_manifest` (now open()+fsync).
