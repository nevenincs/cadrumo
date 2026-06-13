---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` Code Review

SECURE-STORAGE-W04-P07-001 | MEDIUM | Quarantine archive does not preserve new revision metadata
`SecureObjectRow` now defines nullable revision and integrity columns, but `SecureObjectRepository.quarantine_unreadable_rows` still creates `secure_objects_quarantine` with only the legacy metadata shape and inserts only `source_id`, `namespace`, `object_key`, `classification`, `schema_version`, `written_at`, `payload`, and `quarantined_at`. Once W04.P07.S29/S31 start writing or backfilling `revision_id`, prior revision references, hashes, provenance, source events, or conflict policy, quarantining an unreadable row will permanently drop that lineage from the repair archive even though the method contract says it copies all metadata. Not a current HIGH blocker for S28 because the fields are still nullable and unwritten, but this needs an owner before revision writes/backfill are treated as complete.

SECURE-STORAGE-W04-P07-002 | LOW | Bootstrap ALTER path is not race-tolerant
`SecureObjectRepository._ensure_revision_metadata_columns` inspects existing columns once and then executes one `ALTER TABLE ... ADD COLUMN` per missing column. Two first-run processes against the same old-shape SQLite bucket can both observe the same missing column set; the second process can then fail repository construction with a duplicate-column operational error after the first process commits. This is an availability issue rather than data corruption, and it does not invalidate the single-process old-table compatibility regression, but production bootstrap would be safer if duplicate-column failures were re-inspected and treated as success.

SECURE-STORAGE-W04-P07-003 | INFO | HIGH/CRITICAL blocker disposition
The revised repository bootstrap now covers the previous old-shape table breakage for normal repository reads: construction creates/checks `secure_objects`, adds missing nullable revision metadata columns before ORM row loading, and the regression inserts a real encrypted legacy row through production SQLAlchemy column types before loading it through the current repository. Focused secure-object tests, ruff, and diff whitespace checks passed during review.

SECURE-STORAGE-W04-P07-004 | INFO | Follow-up resolution
The MEDIUM quarantine finding was resolved by extending the quarantine table bootstrap and archive insert path to carry the revision metadata columns. The LOW duplicate-column race finding was resolved by re-inspecting after duplicate-column `OperationalError` and accepting it only when the target column exists. Follow-up review found no remaining HIGH, CRITICAL, MEDIUM, or LOW blocker.
