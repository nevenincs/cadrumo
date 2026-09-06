---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:d2dea4429cb5b78094fa6819115fa4aff1f55a42cb1b5e7131e1742102710e86'
step_id: 'S476'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Admit the registry replay parity verb into the bootstrap exempt subtree it belongs to, deriving its qualification from the live spec rather than the family claim, since it declares the registry capability alone with no side effects no write route and profile authentication not applicable, the same posture as the verify and inspect leaves already there

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Changes

`test_a_prefix_exemption_carries_exactly_the_subtree_it_declares[app registry]`
passes; 61 tests in the owning suite pass.

A new verb, `aeat app registry replay-parity`, had landed under a prefix whose
exemption declares its subtree leaf by leaf. The gate's message is not "add the
name" -- it says every leaf under an exempt prefix RUNS WITH NO ACTIVE-PROFILE
SESSION, and to "re-derive whether each still qualifies". So the question was
whether this verb may run unauthenticated, not whether the list was stale.

DERIVED FROM THE LIVE SPEC, NOT FROM THE FAMILY CLAIM. The exemption asserts
`asserts_family_read_only=True`, and it would have been easy to treat that as
covering anything the family later grows. It does not: the subtree is enumerated
precisely so a new leaf is re-examined. Read from `COMMAND_SPECS`:

    app_registry_replay_parity   caps=['registry'] fx=['none'] write=none
                                 destr=False live=False auth=not-applicable

That is character-for-character the posture of `verify`, `verify-filed-state`
and `inspect`, three leaves already declared. It carries no machine secret and
no profile secret.

The handler agrees with the declaration. `verify_replay_parity_cmd` replays the
BUNDLED Renta WEB Open captures through the parity oracle, and its own docstring
states the property: "Offline by construction: the replay driver's only planned
operation is a local parse, and the remote-state guard authorises that plan
before any comparison runs. No AEAT contact occurs on this path." It reads no
profile, session, bucket or secret.

Admitted with that reasoning written beside it, so the next reader sees the
grounds rather than a bare name.

Teeth, two directions, each restored by copy:

* removing the leaf again fails the gate -- the defect verbatim;
* declaring a leaf that resolves to no live verb (`not-a-live-verb`) also fails
  it. The second is the one worth having: without it the gate could be satisfied
  by listing anything at all, and the exemption list is a security surface.

## Notes

PRE-EXISTING, VERIFIED NOT MINE.
`test_config_reset_lifecycle::test_config_reset_start_status_and_resume_exact_durable_journal`
fails with `REFUSED_PROFILE_CUSTODY_TRANSACTION: canonical legal hold owner facts
are absent`. I reverted my change and ran it again: it fails identically without
it. Recorded rather than assumed, because "my edit cannot plausibly have caused
this" is a hypothesis, not evidence.

It is a new candidate for a later firing -- it did not appear in the `src`
sweep, so it arrived with a commit landed since.

STILL OPEN: the two `test_export_split_part_rendering` cases for M200 casillas
00103 and 00199 (filing-grade, so they need S472's care), the export-tree group
stopped in S472 and characterised in S474, the `test_config_reset_lifecycle`
case above, and the three operator decisions -- the 125 `cli.*` extras, the 5
`application.*` extras, and the `tui.ledger.reconciliation.direction` spelling.
