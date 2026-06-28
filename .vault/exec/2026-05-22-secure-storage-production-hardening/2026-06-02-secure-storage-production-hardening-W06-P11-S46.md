---
tags: ['#exec', '#secure-storage-production-hardening']
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S46'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W06.P11.S46 Runtime Adverse-Condition Gates

Wave `W06`; Phase `W06.P11`; Step `S46`.

## Description

- Add runtime factory tests for route/session bucket mismatch refusal.
- Add runtime factory tests for initial unsecured backend refusal.
- Add runtime-created repository tests for unregistered namespace write refusal and no mutation.
- Bind runtime-created `SecureObjectRepository` instances to the live active session.
- Harden runtime-bound repository calls against missing, unsecured, or changed active sessions.
- Add stale-session regression tests for normal writes, raw-key writes, quarantine, and diagnostic surfaces.
- Persist mandatory code-review findings and remediation status.

## Outcome

Step `W06.P11.S46` now verifies and enforces runtime-bound secure-object repository refusal for route mismatch, unregistered namespaces, unsecured backend use, and stale active-session drift. Runtime-created repositories require the secure active session to remain valid across writes, deletes, raw iteration, namespace diagnostics, decryptability probes, failure iteration, and metadata reads.

Validation passed:

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/test_runtime.py`

Mandatory code review completed. Initial HIGH findings for stale write and quarantine paths were remediated; a MEDIUM diagnostic-surface finding was remediated; final review reported no remaining findings and no HIGH or CRITICAL findings.

## Notes

The S46 scope broadened from adverse-condition tests into runtime-bound repository hardening because code review found stale-handle gaps in the implementation. Direct/bootstrap repository construction remains non-strict unless the runtime factory binds the repository to a secure active session.
