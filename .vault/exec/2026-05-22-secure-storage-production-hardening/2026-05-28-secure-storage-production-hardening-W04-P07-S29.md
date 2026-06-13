---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S29'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P07.S29`

Wrote secure-object revision lineage and integrity metadata on save paths.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S29-review.md`

## Description

Secure-object writes now populate `revision_id`, `previous_revision_id`, `previous_payload_hash`, `payload_hash`, `ciphertext_hash`, `revision_written_at`, `write_provenance`, `source_event_id`, and `conflict_policy`.

The implementation records only the actual current conflict policy, `last-write-wins`, because compare-and-swap policy selection belongs to `W04.P07.S30`. Overwrites link to the previous revision id when available, or derive a previous payload hash from a readable legacy row before replacing it.

## Tests

Validation covered natural-key save metadata, overwrite lineage, legacy-row overwrite lineage, batched writes, raw-key archive/restore writes, and rejection of caller-supplied conflict-policy metadata before the CAS contract exists.

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
