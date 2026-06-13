---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S84]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening-W12-P21-S84` Code Review

S84-001 | LOW | Domain helper centralizes adapter-owned runtime construction inside the domain package

`src/aeat/domain/_secure_storage_runtime.py` is a domain module whose only responsibility is to load settings, inspect adapter storage runtime readiness, and return a concrete `SecureObjectRepository`. That helper is then imported by `src/aeat/domain/usage_ratios/_service.py`, so a domain service now depends on a domain-level infrastructure factory instead of the adapter-owned `runtime_repository` boundary. The current behavior still routes through runtime readiness and does not create a raw repository, but this weakens the accepted hexagonal direction and creates a second canonical-looking factory surface beside `src/aeat/adapters/persistence/storage/runtime_repository.py`. Prefer moving the shared helper to the adapter storage runtime boundary or having domain repository code depend on a narrower injected repository/protocol so S84 does not expand adapter construction responsibility inside `src/aeat/domain`.

Resolution: closed before S84 plan-row closure. The domain-level helper was deleted, and usage-ratio persistence now imports the adapter-owned `runtime_repository` factory directly for default bucket-qualified storage resolution.
