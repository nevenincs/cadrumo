---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P07.S28`

Extended the secure-object SQL mapper with nullable revision-lineage and integrity metadata columns.

- Modified: `src/aeat/adapters/persistence/storage/sql/_orm.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P07-S28-S31-review.md`

## Description

`SecureObjectRow` now carries the storage-level metadata required by the architecture decision: `revision_id`, `previous_revision_id`, `previous_payload_hash`, `payload_hash`, `ciphertext_hash`, `revision_written_at`, `write_provenance`, `source_event_id`, and `conflict_policy`.

The columns are nullable at this step because write semantics, conflict handling, and existing-row backfill are handled by adjacent W04.P07 steps.

## Tests

Validation covered fresh SQL schema materialization and the secure-object SQL test module.

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
