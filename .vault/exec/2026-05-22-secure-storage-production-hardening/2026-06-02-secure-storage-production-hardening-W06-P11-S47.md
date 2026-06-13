---
tags: ['#exec', '#secure-storage-production-hardening']
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S47'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W06.P11.S47 Revision Conflict And Remote Mirror Adverse Tests

Wave `W06`; Phase `W06.P11`; Step `S47`.

## Description

- Add provider-backed adverse tests for remote mirror partial upload inspection.
- Add provider-backed adverse tests for remote mirror partial download inspection.
- Add provider-backed adverse tests for remote mirror revision conflict inspection.
- Add raw-key secure-object compare-and-swap stale-revision regression coverage.
- Persist mandatory code-review findings and remediation status.

## Outcome

Step `W06.P11.S47` now covers revision-conflict and partial-remote-mirror adverse cases with real code paths. Remote mirror tests use `LocalFileSystemProvider`, production manifest construction, and typed inspection helpers. Secure-object coverage now proves raw-key compare-and-swap writes refuse stale expected revisions without overwriting the current row and with the translated revision-conflict error key.

Validation passed:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run --no-sync pytest src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`

Mandatory code review completed. Initial MEDIUM and LOW test-quality findings were remediated; final review reported no remaining findings and no HIGH or CRITICAL findings.

## Notes

The existing shared worktree already carried unrelated in-flight edits in remote mirror implementation and legacy mirror tests. This step isolated new S47 mirror coverage in `src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py` and touched `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` only for the raw-key stale revision-conflict regression.
