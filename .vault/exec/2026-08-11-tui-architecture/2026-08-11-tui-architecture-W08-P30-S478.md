---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:78a8d813d31f4e2c2c16752771e76a18f29be13e28658fa0444e9b8ec788cb8c'
step_id: 'S478'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Seed the reset lifecycle profile the way production leaves one, recording the legal hold snapshot through the door that documents the opt-in and refreshing the filing retention snapshot the way persisting a filing does, since the fixture wrote the catalogue directly and produced a profile whose filing exists while its snapshot still says none

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`

## Changes

`test_config_reset_start_status_and_resume_exact_durable_journal` passes.

TWO FIXTURE DEFECTS, ONE BEHIND THE OTHER. The profile the test seeded was not
a profile production can produce, in two independent ways, and the first hid the
second.

FIRST: the custody-transaction deletion preflight joins the legal and filing
hold owners, and an ABSENT legal-hold snapshot fails closed by design -- absence
means nobody was asked, not that no case is open. `register_minimal_profile`
leaves it absent unless asked, and documents `record_empty_legal_hold=True` for
exactly this case: "when a test's subject needs a profile that a
custody-transaction deletion preflight will actually accept". Passed it, with
the reason at the call site.

SECOND, AND ONLY VISIBLE ONCE THE FIRST CLEARED: with the refusal gone the reset
ran to `complete` where the test asserts it pauses on `retention_unresolved`.
`_persist_retained_filing` wrote the catalogue through the repository directly.
Production refreshes the retention snapshot at the moment a filing is persisted
(`modelo.revision_persistence`), because the deletion preflight cannot read a
bucket it has not unlocked and reads that plaintext record instead. So the
fixture produced a profile whose filing exists while its snapshot still says
"no filings" -- and the preflight, reading the snapshot, correctly found nothing
to retain. The fixture now records the snapshot through the same production
recorder.

The test's own assertions were right throughout. It expected a pause on an
unresolved retention, which is what production does when a retained filing
exists; the fixture simply never built that state.

Teeth, one per half, each restored by copy: dropping the legal-hold opt-in
returns the custody refusal, and removing the retention-snapshot refresh returns
the premature `complete`.

## Notes

I MOVED A DELETION PREFLIGHT FROM REFUSE TO PASS, which is the less safe
direction and deserves saying plainly. It is sound here only because the
refusal was an artefact of a profile production never creates: a real
registration records the legal-hold snapshot at `registration.py:329`, so a real
profile always carries one. The guard itself is untouched and still fails closed
on absence -- the second teeth case above is the proof.

A CONTRADICTION I FOUND AND DID NOT ACT ON, because it is an owner's call.
`register_minimal_profile` documents its default as a ruling: "production
registration records no such fact -- the legal-case owner has no creation-time
writer anywhere in the tree". That is no longer true. `registration.py:329`
calls `try_record_legal_hold_snapshot(bucket_id=..., open_case_ids=(), ...)`
with its own comment explaining why "zero known cases" is a fact for a
brand-new profile. So the seeding door's stated premise for leaving the default
`False` has gone, and every profile it seeds now differs from a real one in
exactly the way its docstring says it avoids for the filing owner.

Flipping that default would make every seeded profile deletable, which the same
docstring warns "silently erases the fail-closed gap production still has" --
a warning written when production had that gap. Whether it still does is a
custody judgement about a data-destruction path, so I passed the documented
opt-in for this one test and left the default alone.

PRE-EXISTING, VERIFIED NOT MINE:
`test_custody_transactions::test_delete_owner_receipts_are_durable_and_idempotent`
and `::test_owner_receipts_resume_after_owner_effect_precedes_journal_state`
fail identically with my change reverted.

STILL OPEN: those two custody cases, the export-tree group stopped in S472 and
characterised in S474, and the three operator decisions -- the 125 `cli.*`
extras, the 5 `application.*` extras, and the
`tui.ledger.reconciliation.direction` spelling.
