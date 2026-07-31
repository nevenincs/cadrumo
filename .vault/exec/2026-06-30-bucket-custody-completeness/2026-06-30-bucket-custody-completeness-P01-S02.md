---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:7d393af70f3880e37c8a8b02f73d3f6bd62d81fd56789b4a124816004bfe6d3d'
step_id: 'S02'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Declare custody_disposition on every namespace definition in the registry

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Declare `custody_disposition` on every registered namespace.
- Classify cross-period calculation inputs and structured profile/history stores
  as `STRUCTURED_CUSTODY`.
- Classify evidence bytes, live snapshots, AEAT artefacts, and bucket event
  history as `FULL_CUSTODY_ONLY`.
- Classify the participation index as `DERIVED_REBUILDABLE`.
- Classify workflow/session/test/cache/secret integration state as
  `PROCESS_LOCAL`.
- Add a registry test proving every namespace declaration sets the field
  explicitly.

## Outcome

P01.S02 is complete. The carry policy is now declared in the canonical namespace
registry instead of being inferred by later transports from ad hoc lists.

Verification:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`

The final touched-surface pytest run passed with 56 tests, including the
namespace registry, namespace adoption, and SQL secure-object split test
surfaces. Ruff passed after mechanical import ordering.

## Notes

Classification remains conservative. The cleartext structured profile is not yet
wired to emit its not-a-full-backup notice; that belongs to the transport wiring
phase.
