---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:7ea1b24355703db28b0bf1a7da99d25b067e4145edd03e5255b8c6cc77351170'
step_id: 'S205'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh settle whether a seeded profile should also carry an empty legal-hold snapshot, since the seeding door now records the empty filing-retention snapshot registration records but deletion still refuses three reset targets on a legal or filing hold, and an absent legal-hold snapshot means nobody has been asked rather than no holds exist so the refusal is the fail-closed design working, which makes this a question about what the seeding door owes rather than a defect in the guard

## Scope

- `src/cadrumo/tests/user_profile.py and src/cadrumo/application/evidence/_profile_legal_hold.py`

## Description

- Read the production registration path (`application/user_profile/_registration.py`)
  to establish, rather than assume, what it records at profile-creation time.
- Confirm the `S156` ruling still holds against current code: `LegalHoldCaseAuthority.record_open_case_snapshot`
  has zero production call sites anywhere in the tree.
- Add an opt-in `record_empty_legal_hold` parameter to `register_minimal_profile`,
  default `False`, matching production's silence on the legal-hold fact.
- Prove, from outside the repository, that the default stays fail-closed, the
  opt-in makes a seeded profile deletion-assessable, and a genuine open case
  recorded afterwards still refuses deletion.

## Outcome

**Production records no legal-hold fact anywhere, confirmed by reading the
registration path directly rather than by inheriting the `S156`/`S188`
ruling.** `application/user_profile/_registration.py` calls
`try_record_filing_retention_snapshot` at registration and nothing else that
touches `LegalHoldCaseAuthority`. A repo-wide search for
`record_open_case_snapshot` and `LegalHoldCaseAuthority(` outside test code
turns up exactly zero production call sites — only the owning module itself
and test helpers. This is the same fact `S156` ruled on ("the legal-case
owner has none anywhere in production, so a real registered profile carries
no legal snapshot either") and `S188` already acted on for the shared
seeding door (deliberately NOT recording it there), re-verified against
today's tree rather than assumed current.

**The judgement: the seeding door stays production-faithful, and the tests
that need a deletable seeded profile must ask for that explicitly.** Because
production has no legal-hold writer, a seeded profile that could pass a
custody-transaction deletion preflight by default would assert a state real
profiles cannot reach — the fabricated-fixture failure mode this campaign has
rejected twice already (per `S188`'s own notes). `register_minimal_profile`
therefore gained `record_empty_legal_hold: bool = False`; left at its default
it changes nothing. When a caller passes `True`, the door records an empty
open-case snapshot for the legal owner through the exact same production
recorder (`LegalHoldCaseAuthority.record_open_case_snapshot`) it already uses
for the filing owner, asserting nothing stronger than "the legal owner was
asked and had nothing to report" — the same class of fact `S188` already
records for the filing owner. The parameter is scoped to this row's
ownership (`src/cadrumo/tests/user_profile.py`); no consumer was switched to
it, since doing so is a per-caller judgement about what each test's subject
actually needs, and belongs to whichever row owns that call site.

**Three-way proof, all real, all outside the repository.** A scratch script
(not a tracked test, per the campaign's "don't let a broad sweep capture a
mutation" caution) drives three profiles through the real custody-transaction
deletion preflight (`ProfileCapsuleLifecycle.prepare_delete`, the one join of
the legal AND filing hold owners — distinct from `BucketMaintenanceService.assess_deletion`,
which only ever consulted the filing-only retention floor):

1. Default seeding (`record_empty_legal_hold` unset): the preflight refuses,
   `canonical legal hold owner facts are absent` — exactly production's
   fail-closed behaviour, unchanged.
2. Opt-in seeding (`record_empty_legal_hold=True`): the preflight succeeds
   and returns a journal, because both owners now hold a recorded (here
   empty) fact.
3. Opt-in seeding, then a REAL open case recorded afterward
   (`open_case_ids=("real-open-case-2026-08-15",)`): the preflight refuses
   again, `a legal or filing hold blocks local profile deletion` — proving
   the flag records an empty snapshot, not a bypass; a genuine hold still
   blocks exactly as before.

All three passed on the first run against real storage (`isolated_profile_storage_root`),
real capsule publication (`open_test_profile_session` + `register_minimal_profile`),
and the real production preflight — no mocks, fakes, or stubs anywhere in the
proof.

## Notes

**This row does not touch `src/cadrumo/application/evidence/_profile_legal_hold.py`.**
It was read in full to confirm `S156`'s ruling and the shape of
`record_open_case_snapshot` before wiring the opt-in, but the row's judgement
is that the module needs no change: it already exposes exactly the write and
read surface both the filing-owner pattern and this row's opt-in reuse.

**Two known-wrong consumers named by the `S188` outcome remain untouched, on
purpose — they are not this row's ownership.**
`application/bucket_maintenance/tests/test_service_assess_deletion.py::test_a_recorded_empty_snapshot_answers_while_an_absent_one_refuses`
still proves filing-retention absence by relying on the seeding door's
silence, which is no longer true since `S188` landed; it needs to forge
absence explicitly (delete the recorded filing snapshot) rather than depend
on it. That file is outside this row's ownership and was reported, not
edited, exactly as `S188` already reported it. Nothing in that file concerns
the legal-hold question this row answers.

**The "three reset targets" named in the row's framing were investigated and
found already correctly handled**, not left broken. `application/tests/test_config_reset.py`'s
own local helpers (`_create_profile`, `_delete_profile_through_custody`)
already record an empty legal-hold snapshot directly via `LegalHoldCaseAuthority`,
with a comment at the site giving the same reason this row's ruling gives:
production has no legal-hold writer, so it cannot be recorded at the shared
seeding door. That file needed no change; its authors had already reached the
same ruling this row independently re-derives and now gives an ergonomic,
reusable shape to.

**No git action taken.** Only `src/cadrumo/tests/user_profile.py` was
modified for this row; nothing was staged, committed, or reverted.
