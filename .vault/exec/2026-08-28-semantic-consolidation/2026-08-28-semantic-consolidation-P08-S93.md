---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c7cd8c2c23ed35ff24c9fb02ac407c54c9c7e514759f787eafcdf9c5d3b10ffc'
step_id: 'S93'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Run both stale-pin sweeps after every namespace retirement rather than once, since each retirement creates new stale pins

## Scope

- `src/cadrumo/`
- `dev/`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/tests/test_co_commit_carries_its_revision.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_every_composing_write_is_declared.py`
- `M` `src/cadrumo/domain/buckets/tests/test_no_bare_event_append_save.py`
- `M` `dev/identity/tests/test_identifier_namespace_enrollment_gate.py`
- `M` `dev/tests/test_invoice_iva_validation_owner_census.py`
- `verify:` `pytest <the five gates> -n 0 -m ""` -> `pass` (one pre-existing failure, see Notes)

## Notes

`test_every_composing_write_carries_a_revision_or_is_declared` remains red on two
`application/modelo/_edit_execution.py` functions that compose a secure-object
write without asserting a revision. That predates this campaign and needs an
architectural ruling rather than a mechanical sweep; tracked as its own Step.

The identifier-enrolment gate keeps one stale adjudication naming
`domain/modelos/_ledger_filing_snapshot.py`, which rides with the held modelos
commit.
