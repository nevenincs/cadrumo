---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:637c26e59a9b0ed0e61b943b8a44a8c337efbb9dc934d96325a60a87d4e0400e'
step_id: 'S115'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Search the test corpus for assertions that a taxonomy-declared storage location is never created, via both the storage_path accessor and direct settings-field reads, classify each hit as a genuine dormancy claim or a refusal-guard/setup-baseline false positive, then write and land an accessor-routed persist-then-assert-absent test for each confirmed dormant category a real writer could ever populate

## Scope

- `src/cadrumo/domain/filing/tests/test_secure_storage_roundtrip.py`
- `src/cadrumo/adapters/persistence/profile/tests/test_justificante_repository.py`

## Description

- Swept the test corpus for `assert not storage_path(StorageCategory.X)...` (accessor-qualified) and `assert not settings.cadrumo_X_dir...` (settings-field-qualified) forms, enumerating every hit tree-wide rather than sampling by category name.
- Classified each of the three accessor-qualified hits: `ATTACHMENTS` genuine (proves `AttachmentStore.put_file()` persists only to the encrypted secure-object database); `LOGS` and `USAGE_RATIOS` false positives (test-setup baselines for the occupancy-inventory fixture, not architectural claims).
- Queried `STORAGE_TAXONOMY` directly and found `DRAFTS`, `JUSTIFICANTES`, `ATTACHMENTS`, and `ATTACHMENTS_MANIFESTS` all declare `consumer_module = "adapters/persistence/storage/_rotation.py"` and nothing else -- all four, not the two originally hypothesised. Confirmed by reading (read-only) `default_rotation_plan()` that this function only walks the directories to re-encrypt `.envelope.json` files on key rotation; it is a sweep, not a writer.
- Corroborated with production evidence: `adapters/persistence/profile/filing_drafts.py` and `adapters/persistence/profile/justificante.py` both carry a module docstring stating "no plaintext ... JSON or envelope file lands on disk" -- the same architecture the one existing `ATTACHMENTS` test already proves.
- Wrote `test_filing_draft_persists_only_to_the_secure_database_object` in `test_secure_storage_roundtrip.py` and `test_save_persists_only_to_the_secure_database_object` in `test_justificante_repository.py`, both modelled on the existing `test_put_file_reads_source_but_persists_only_secure_database_object` shape: persist a real record through the production repository, confirm the SQL side received it (`repo.load(...) == original`), then assert `not storage_path(StorageCategory.X).exists()`. Routed the absence check through the accessor rather than a literal, since a stale literal after a future taxonomy subpath move would find nothing and pass vacuously.
- Verified each assertion is a real check, not a vacuous one: measured live (outside pytest) that `storage_path(StorageCategory.DRAFTS)` / `storage_path(StorageCategory.JUSTIFICANTES)` resolve to paths that do not exist before any write, inside the same `isolated_runtime_profile` context the tests use.
- Checked `ATTACHMENTS_MANIFESTS` for a real writer before deciding whether to add a fourth test: exactly two references to `StorageCategory.ATTACHMENTS_MANIFESTS` exist in the whole tree (the `_rotation.py` dirname derivation and the taxonomy declaration itself). `AttachmentStore.write_manifest` / `manifests_dir` resolve through `secure_object_namespace_logical_path`, a SQL-logical key prefix inside `secure_objects`, structurally unrelated to this filesystem category. No production path can ever populate it, so no test was written for it -- an assertion with no exercised production path would be worse than no test.
- Both new tests ran green (`test_secure_storage_roundtrip.py`: 4 passed; `test_justificante_repository.py`: 13 passed) and `ruff check` passed clean on both files before landing.

## Outcome

`ATTACHMENTS` was already proven by an existing test. `DRAFTS` and `JUSTIFICANTES` are now proven by the two new tests above. `ATTACHMENTS_MANIFESTS` has no real writer and correctly carries no test. All four of the taxonomy members whose sole declared consumer is `_rotation.py`'s rotation sweep are now accounted for by direct evidence rather than by inference from a docstring or a declared-consumer field alone.

## Notes

Both new tests landed inside commit `f9cb8468c7` ("test(storage): classify the \"logs\" literal split for S78"), whose subject describes only an unrelated literal-split band. The commit was authored as a rescue of nine dirty working-tree files after an authoring session hit its limit; the rescue verified the staged file set matched what was intended to be staged, but the commit message was written from a `--stat` line-count read plus one sampled diff, not from opening every file, so it undersold its own diff by two full test additions. `git show f9cb8468c7 -- <path>` on either file surfaces the addition in full; searching by the test function names above (`test_filing_draft_persists_only_to_the_secure_database_object`, `test_save_persists_only_to_the_secure_database_object`) or by this exec record is the reliable way to find the change, since the commit subject will not.
