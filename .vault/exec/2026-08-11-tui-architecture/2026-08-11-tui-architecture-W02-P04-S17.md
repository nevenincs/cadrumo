---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:97390f06467702b75c1991866f4b3d90e8ac1c37af8ad497393002ac860c77a1'
step_id: 'S17'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define lifecycle journal, ordered event stream, owner lease, compare-and-swap revision, and secure reference ports

## Scope

- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/_leases.py`
- `src/cadrumo/application/operations/_replay.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_journal.py`
- `src/cadrumo/application/operations/tests/test_facade.py`

## Description

- Preserve the extracted journal, replay, and lease owners; expose their approved contracts only from the operations facade.
- Add caller-timestamped, UTC-aware `ABSENT`, `ACTIVE`, and `EXPIRED` lease observations carrying the exact optional lease witness and derived canonical evidence reference.
- Define absent-only acquisition, exact-predecessor renewal/takeover compare-and-swap, and exact-predecessor release ports. The compare-and-swap predecessor is never optional.
- Validate transition witnesses: active conflict, expired refusal, renewal identity and extension, expired-predecessor takeover with a new owner and token, owner loss, and release.
- Derive every lease evidence reference from a versioned canonical transition payload and caller-supplied observation time; add real production-model signature and mutation tests without test doubles.

## Outcome

The application contract can now report targetable absent, active, and expired lease state, and persist adapters have an exact caller-clocked transition vocabulary without a hidden clock, storage-generated identity, or adapter policy. S19 remains the only owner of adapter atomicity and durable implementation.

## Verification

- `uv run pytest src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py -q` - 15 passed in 4.74s after exact production introspection pinned every lease protocol parameter and return annotation.
- `uv run ruff check src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/_leases.py src/cadrumo/application/operations/_replay.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - all checks passed.
- `uv run ruff format --check src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/_leases.py src/cadrumo/application/operations/_replay.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - 6 files already formatted.
- `uv run basedpyright src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/_leases.py src/cadrumo/application/operations/_replay.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - 0 errors, 0 warnings, 0 notes.
- `uvx vaultspec-core vault check all` - exit 0; 1,376 shared-corpus advisory warnings, no structural or conformance failure.

## Notes

Grounded against ADR D5 and the reopened S17 audit. Semantic search confirmed the profile custody pointer and auth acquisition lock as related exact-observation/CAS patterns, while the operation contract remains independent and does not import their storage mechanisms. The Step state was left untouched for the supervising executor.

