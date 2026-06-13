---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---

# `secure-storage-production-hardening` Code Review

S19-001 | MEDIUM | Repository construction guard missed constructor aliases

Reviewer found that the first guard only detected calls whose AST call name was literally `SecureObjectRepository`, allowing a production file to import the class under another name and construct it directly. Resolved by collecting direct import aliases and simple local aliases before evaluating constructor calls.

Status: resolved.

S19-002 | MEDIUM | Runtime allowlist accepted `engine=None`

Reviewer found that the runtime allowlist only verified an `engine` keyword existed, so a runtime constructor could pass `engine=None` and fall back to ambient engine routing. Resolved by rejecting literal `engine=None` in the allowlisted runtime constructor call.

Status: resolved.

S19-003 | MEDIUM | Repository construction guard missed SQL module aliases from storage package

Reviewer found that the tightened guard still missed `from aeat.adapters.persistence.storage import sql as storage_sql` followed by `storage_sql.SecureObjectRepository()`. Resolved by treating the storage package's exported `sql` module as a module alias source.

Status: resolved.

S19-004 | INFO | Review and validation status

Reviewers found no HIGH or CRITICAL issues in the S19 slice. The migrated auth and Google production sites route through `secure_object_repository_for_active_bucket()` and retain active-profile/session readiness checks.

Focused code validation passed. The required locale audit was invoked through `python -m aeat.locales audit`; it currently reports unrelated Hungarian parity gaps in the shared worktree, outside the S19 secure-repository-construction slice.
