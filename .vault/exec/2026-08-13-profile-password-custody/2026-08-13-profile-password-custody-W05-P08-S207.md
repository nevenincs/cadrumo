---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ec9e9b6e42079c08acb7bb6a776c2abecbd9d50dc85db1042bede3d113cfd4bd'
step_id: 'S207'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh give the legal-hold evidence arm a production producer, since the custody hold authority joins a filing projection that has two real writers with a legal projection that has none, the recorder having zero callers anywhere outside its own module so its snapshot file never exists, its projection raises on the absence and the transaction converts that to a refusal, which means no profile can be deleted by any route today and the all-profile reset shares the same three primitives so the campaign's closing destructive step is blocked behind it as well

## Scope

- `src/cadrumo/application/evidence/_profile_legal_hold.py and src/cadrumo/application/user_profile/_custody_hold.py and src/cadrumo/application/user_profile/_registration.py`

## Description

- Add a best-effort producer, `try_record_legal_hold_snapshot`, to
  `_profile_legal_hold.py`, mirroring `try_record_filing_retention_snapshot`
  exactly: same never-raise contract, same reason (a caller that exists to do
  something else must never be refused over a deletion-support record).
- Export it through the `application.evidence` facade's `__all__`.
- Call it from `_registration.py`, right after the existing filing-retention
  call, recording `open_case_ids=()` — an empty, not invented, fact.
- Rule, in the function's own docstring, why an empty snapshot at
  registration is honest rather than fail-open, and what it does NOT close.
- Prove, from outside the repository and against the real production
  registration door, that a freshly registered profile is now
  deletion-assessable, that a real open case afterward still refuses
  deletion, and that the gate bites (reverting the call reproduces the
  pre-fix universal refusal).
- Add one tracked, real-behaviour test to
  `application/user_profile/tests/test_registration.py` proving the same
  claim through the production `register_profile_with_credentials` door.
- Leave `_custody_hold.py` unmodified — it was read to confirm the join
  shape and needed no change — and leave `_custody_service.py` untouched
  entirely, per the explicit ownership boundary.

## Outcome

**The defect was real and not previously named: no profile could be deleted
by any route.** `LegalHoldCaseAuthority.record_open_case_snapshot` had
exactly one occurrence in the entire tree before this row — its own
definition. `_custody_hold.py`'s `ProfileCustodyHoldAuthority.assess` joins a
legal projection and a filing projection; the filing one had two producers
(`user_profile/_registration.py` and `modelo/_revision_persistence.py`), the
legal one had none, so `LegalHoldCaseAuthority.project` raised
`FileNotFoundError` for every profile that ever existed, converted by
`_custody_hold.py` into `canonical legal hold owner facts are absent`, which
`_custody_service.py`'s `prepare_delete` converts into an unconditional
refusal. This is confirmed, not inferred, by the gate-bites proof below: a
FRESH, REALLY registered profile — no seeding door, no test fixture — could
not pass the deletion preflight before this row.

**The ruling: an empty snapshot at registration is honest, not fail-open,
and it is a partial answer, not the whole one.** The distinction the row
asked for: a profile at the instant of registration has no filings and no
captured AEAT expedientes, so there is structurally nothing yet for an
outside legal hold to be a hold ON. "Zero known open cases" recorded at that
instant is therefore the same class of fact
`try_record_filing_retention_snapshot` already records for a brand-new
profile's filing history ("no filings exist," not "nobody checked") — not an
assumption of clearance about the taxpayer's life. That argument does NOT
extend past the instant it is recorded: once a profile has real filings or
captured AEAT proceedings, this registration-time fact goes stale the moment
either changes, and nothing today refreshes it. There is no capture-time
producer wired to `application/live/_expedientes.py` (Population A,
"derivable today" per the row this campaign already ruled on) and no
operator-affirmation surface for a genuinely external hold (Population B).
Both remain open follow-on work; this row closes "no profile can ever be
deleted," not "every legal hold is tracked."

**The producer is a straight mirror of the filing-retention pattern, sharing
its asymmetry and its safety argument.** `try_record_legal_hold_snapshot`
swallows every exception and logs, exactly like its filing sibling, because
neither caller exists to serve deletion and a registration REFUSED over a
deletion-support record is worse than one whose snapshot is missing (which
merely fails closed later, unchanged from today). It never invents case
identifiers — the sole caller passes `()`, an empty, not fabricated, set —
satisfying the constraint that `record_open_case_snapshot` only ever persists
identifiers supplied from outside the application.

**Four-way proof, all real, all from outside the repository, plus one
tracked test.** Against the real `register_profile_with_credentials` door and
real storage (no seeding-door shortcut):

1. A freshly registered profile's legal-hold snapshot now exists and is
   empty (`LegalHoldCaseAuthority.project(...).blocks_local_deletion is
   False`), where before it raised `FileNotFoundError`.
2. That same profile now passes the real custody-transaction deletion
   preflight (`ProfileCapsuleLifecycle.prepare_delete`) — the actual join of
   the legal AND filing hold owners.
3. A REAL open case recorded afterward (`open_case_ids=("real-open-case...",)`)
   still refuses deletion with `a legal or filing hold blocks local profile
   deletion` — the producer records an empty snapshot, not a bypass.
4. Gate bites: reverting the new call at runtime (a monkeypatch of the
   imported name inside `_registration`, from outside the repository, no
   tracked file touched) reproduces the exact pre-fix universal refusal,
   `canonical legal hold owner facts are absent`.

The tracked test `test_registration_records_zero_known_open_legal_cases` in
`application/user_profile/tests/test_registration.py` asserts (1) and (2)
through the same production door and passes; the same external-plugin
technique applied to it reproduces its own red under the pre-fix behaviour.

## Notes

**`_custody_hold.py` needed no change.** It already joins the legal and
filing projections correctly; the defect was entirely upstream, in the
absence of a legal-arm writer. Read in full to confirm the join shape before
concluding this, not assumed from the row's own framing.

**`_custody_service.py` was not touched**, per the explicit ownership
boundary — `prepare_delete`'s refusal-conversion behaviour is unchanged and
correct; it was never the defect.

**The all-profile reset's dependency on this primitive was not directly
exercised.** The row's framing named it as a strong inference, not an
observation, and this row does not run a destructive reset to confirm it —
that stays out of scope for a row whose subject is the producer, not the
reset path. `application/tests/test_config_reset.py`'s own suite (already
green before this row, confirmed unaffected after) records legal-hold
directly in its own local helper and does not depend on this new
registration-time write either way.

**Test-seeded profiles are unaffected by this row.** `register_minimal_profile`
(the shared test seeding door, `S205`) does not call
`register_profile_with_credentials` — it publishes a capsule directly and
bypasses production registration entirely — so this row's producer does not
reach it. `register_cli_profile` (the CLI-adjacent seeding door, same file)
DOES call `register_profile_with_credentials`, so CLI-registered test
profiles now also pick up the empty legal-hold snapshot as a side effect;
this was not required by this row's scope but is consistent with it and
introduces no new behaviour beyond what production registration itself now
does for every real profile.

**No git action taken.** Only `src/cadrumo/application/evidence/_profile_legal_hold.py`,
`src/cadrumo/application/evidence/__init__.py`,
`src/cadrumo/application/user_profile/_registration.py`, and
`src/cadrumo/application/user_profile/tests/test_registration.py` were
modified for this row; nothing was staged, committed, or reverted. (The
`evidence/__init__.py` facade edit was necessary to export the new producer
and is outside the row's literally-scoped three files but is the minimum
surface needed to reach `_registration.py` through the canonical facade
rather than a private cross-package import.)
