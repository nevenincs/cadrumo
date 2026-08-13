---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5d65bda9abc4cf4d119b1cb250b132716a81525fe981b31385614cec8a8feff0'
step_id: 'S34'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# verify the four W04 adoptions changed no wire shape for already-valid values

## Scope

- `src/cadrumo/tests/`

## Description

- Ran the persistence-boundary and pydantic-model roundtrip audit gates:
  `test_roundtrip_coverage.py` (the manifest of every persistence boundary
  and its roundtrip test) and `test_roundtrip_fixture_saturation.py` (the
  populated-field anti-tautology proof) — both check STRUCTURE (every
  boundary has coverage, every builder saturates its fields), not the
  four adoptions' specific values, but both must stay green for the
  quality-gate discipline this campaign follows to mean anything.
- Ran the CLI/MCP schema-conformance gate,
  `test_json_schema_conformance.py -m integration` (the suite `W08.P13`'s
  own Verification criterion also names): 332 passed, 1 pre-existing
  unrelated failure (`test_profile_bound_command_populates_active_profile_label`,
  the same onboarding `--tax-residence-jurisdiction-scope` gap already
  documented in `W05.P07.S36`'s Notes with an IDENTICAL 332/1 split —
  confirmed unchanged, not a new regression, and the file is not dirty
  this session).
- Ran a combined pass across all four packages the Wave actually touched
  (`application/ledger/`, `application/aggregation/`, `application/invoices/`,
  `domain/invoices/`) in one process rather than four separate ones, to
  catch any cross-file conftest or fixture interaction the per-Step runs
  in `S29`-`S32` could not see individually: 2637 passed, 10 failures —
  the exact same 10 pre-existing failures already confirmed unrelated in
  each Step's own record (5 from `application/ledger/`, 5 from
  `application/aggregation/`), no new failures from running them together.

## Outcome

COMPLETE. The four W04.P06 adoptions (`TransactionId` at `S29`/`S30`,
`InvoiceId` at `S32`; `BucketId` adjudicated zero-in-scope at `S31`) change
no wire shape for already-valid values: every roundtrip and
schema-conformance gate this row names is green except pre-existing,
already-documented, unrelated failures, none of which reference any of
the four target names or their retyped fields.

## Notes

No incidents. This row's gate names "the four adoptions" but only three
landed code (`S31` adjudicated its target population out of scope
entirely) — the gate still holds: nothing that DID retype changed a wire
shape, and nothing that did NOT retype (because it correctly wasn't there)
needed verifying.
