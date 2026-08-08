---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:360a4ba41bdf80286508bfe75cb18909e6137a6236221e57fb8beb3583756471'
step_id: 'S12'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the three new leaves to the reviewed-non-mutating roster as pure reads over persisted snapshots, verified by test_every_app_leaf_is_accounted_for_by_name_independent_census and a new CLI integration test asserting the three verb shapes

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`

## Description

- Verify rather than author: the roster enrolment and the integration test for
  this row were already on disk.
- Confirm the three leaves are enrolled in the reviewed-non-mutating roster.
- Run the name-independent leaf census the row names as its gate, and triage
  its result rather than reporting the module's pass or fail.

## Outcome

The three leaves are enrolled in the roster in
`src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`, and the
integration module asserting the three verb shapes exists with eight tests, all
passing in the integration lane.

The named census gate is RED, and it is red for reasons that have nothing to do
with this row. Its unaccounted-leaf set contains eight leaves, every one of them
in a peer's ledger-counterparty and ledger-evidence surface, and no deudas leaf
appears in it. Read at the granularity this row cares about, the gate's verdict
on deudas is that all three leaves are accounted for: the census is a set
difference, and deudas is absent from the difference.

Recording the distinction rather than the module result, because "the gate is
red" and "the gate rejects this row's contribution" are different facts and only
the second would block this row.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py -m integration -n0 -q
    2 failed, 18 passed in 123.38s (0:02:03)

The two failures, with their full offender sets extracted from the assertion
messages rather than read off the top of the list:

    test_every_app_leaf_is_accounted_for_by_name_independent_census
      unaccounted: app ledger counterparty confirm, app ledger counterparty show,
      app ledger counterparty withdraw, app ledger evidence batch,
      app ledger evidence consent list, app ledger evidence consent rederive,
      app ledger evidence review list, app ledger evidence review show

    test_every_unambiguously_mutating_app_leaf_is_guarded_or_bootstrap_exempt
      unguarded: app ledger counterparty confirm

Eight of eight and one of one are ledger-counterparty or ledger-evidence leaves.
Zero are deudas. Both files carrying that surface were dirty in the working tree
while this record was written, which is consistent with an in-flight peer lane.

    rg -n "deudas" src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py
    611:        "app live deudas latest",
    612:        "app live deudas list",
    613:        "app live deudas view",

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_live_deudas_verbs.py -m integration -n0 -q
    8 passed in 6.97s

## Notes

The roster enrolment landed in commit `ed09a6dd4b` ("feat(cadrumo): land the
in-flight source work") and the integration test module in `4e8f820065`
("test(cli): exercise the deudas read verbs against isolated local storage").
Neither commit subject names this row.

The census gate stays red on the peer leaves listed above. That is not this
row's debt and was not touched: the two files carrying it belong to an active
peer lane.
