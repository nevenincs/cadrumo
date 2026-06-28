---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S458'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S458 - Replace stale custody and recovery guidance

Scope: replace stale custody and recovery guidance with canonical config custody
verbs and locale-backed recovery copy across master-key, runtime, error-registry,
and locale surfaces.

## Description

- Replaced master-key recovery and rotation guidance with `aeat config recover`
  and `aeat config rekey` operator commands.
- Replaced storage-session reactivation guidance with `aeat config unlock NAME`
  in active-session, runtime-readiness, error-registry, and runtime locale text.
- Updated storage error-registry suggestions for expired sessions, missing active
  sessions, locked buckets, and recovery verification to point at the first-class
  custody verbs.
- Updated storage runtime and storage-refusal locale strings through
  `python -m aeat.locales set`; repaired a PowerShell backtick escaping accident
  and re-ran the locale audit to prove the catalogues parse.
- Updated focused master-key expectations for the canonical recovery command.

## Outcome

Stale operator guidance in the secure-storage custody substrate no longer points
at vague recovery prose or the older `config profile switch` remediation where a
first-class custody verb now exists. Runtime readiness and storage error
surfaces tell operators to use `config unlock`, while recovery and rekey
material points at `config recover` and `config rekey`.

Validation:

- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_active_session.py src/aeat/adapters/persistence/storage/master_key/_master_key.py src/aeat/adapters/persistence/storage/master_key/_master_key_bucket_dek.py src/aeat/adapters/persistence/storage/runtime.py src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py src/aeat/adapters/persistence/storage/master_key/tests/test_adverse_sessions.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py src/aeat/adapters/persistence/storage/master_key/tests/test_adverse_sessions.py -q`
- `uv run --no-sync pytest src/aeat/core/errors/tests/test_registry.py src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/entrypoints/cli/tests/test_error_registry_contract.py -q`

## Notes

The locale command must be invoked with PowerShell single-quoted values when the
string contains Markdown-style backticks. A first pass with double-quoted values
converted `` `a`` into a BEL control character; the affected entries were
mechanically repaired, then set again through `python -m aeat.locales set` and
validated by `python -m aeat.locales audit`.
