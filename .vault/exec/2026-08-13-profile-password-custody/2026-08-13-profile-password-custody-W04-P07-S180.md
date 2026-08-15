---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:86b165c92e8b5292a77948cec6a6d2cd77589317ddf8ad0ec65ab1e0e4170aff'
step_id: 'S180'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh strike the two second version literals the new single-declaration detector found mechanically and name the one persisted format that still authors its number anonymously, the remote mirror namespace manifest and the custody owner receipt each defaulting a version beside a constant their own siblings already bind, and the custody hold evidence carrying a bare literal that leaves it unbindable into the enrolment tables despite its class already being argued

## Scope

- `src/cadrumo/adapters/outbound/storage/_records.py and src/cadrumo/application/user_profile/_custody_transactions.py and src/cadrumo/application/user_profile/_custody_hold_models.py`

## Description

- Verify each of the three sites against current source, then classify per-site
  whether the field is read back through the typed model.
- `RemoteMirrorNamespaceManifest.manifest_schema_version`: remove the default
  entirely rather than pointing it at the constant; both production
  construction sites already stamp the constant explicitly, so only tests
  needed sweeping.
- `ProfileCustodyOwnerReceipt.schema_version`: remove the default; stamp the
  constant explicitly at the sole production construction site.
- `ProfileCustodyHoldEvidence.schema_version`: add a named module-level
  constant and bind the existing default to it by name, leaving the default in
  place.
- Sweep every construction site the removed defaults now require, in
  production and tests.
- Prove the fix bites from a scratchpad script outside the repository.

## Outcome

**S158's read-tolerance finding held for both required-field sites, and did
not apply to the third.** Read-back was the deciding fact, not proximity or
class:

- `RemoteMirrorNamespaceManifest.manifest_schema_version` **is** read back:
  `get_remote_mirror_namespace_manifest` calls
  `RemoteMirrorNamespaceManifest.model_validate_json(payload)` on bytes fetched
  from the remote provider, then separately compares the parsed field against
  `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION` and raises
  `OutboundStorageIntegrityError` on a mismatch. That explicit check only
  catches a payload that DISAGREES with the current version; a payload
  MISSING the field entirely (a torn or truncated remote write) would have
  validated as whichever number the default held, silently matching
  "current" for as long as the constant stayed at that number. Applying
  S158's reasoning, the field is now required with no default
  (`Field(ge=1)`, no `default=`) rather than bound to the constant. Both
  production construction sites (`build_remote_mirror_namespace_manifest` and
  the empty-namespace fallback in `_load_remote_manifest`) already stamped
  `manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION` explicitly,
  so no production sweep was needed. `get_remote_mirror_namespace_manifest`
  already wraps any `ValidationError` from the parse into
  `OutboundStorageIntegrityError`, so an absent field now surfaces through the
  exact refusal path a disagreeing field already used -- no new error
  handling was required.
- `ProfileCustodyOwnerReceipt.schema_version` **is** read back:
  `_custody_repository.py`'s `load_owner_receipt` calls
  `ProfileCustodyOwnerReceipt.model_validate_json(...)` on the on-disk owner
  receipt. The same silent-hydration defect applied, so the field is now
  required with no default. There was exactly one production construction
  site, `_custody_service.py`'s `_record_owner_effect`, which now stamps
  `schema_version=CUSTODY_RECEIPT_SCHEMA_VERSION` explicitly. No test
  constructs this model directly (it is exercised only through the delete/
  create service flow), so no test sweep was needed beyond the production
  call site.
- `ProfileCustodyHoldEvidence.schema_version` is **not** read back:
  `_custody_hold.py`'s `_ProfileCustodyHoldEvidenceOwner.refresh()`
  unconditionally recomputes the evidence from the live external-owner
  projection and writes it; there is no `load()` counterpart anywhere in the
  tree that parses the on-disk file back through the typed model. This
  matches the closed `S161` ADR's classification (REGENERABLE: delete-and-
  refuse is the correct response to an unreadable file, since a fresh one is
  always recomputable). With no read-back, S158's stronger fix does not apply
  here -- a default bound to a named constant is sufficient, since the
  literal's only defect was being unnamed, not being read-tolerant. Added
  `CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION` in the same module and pointed the
  field's existing default at it by name.

**Construction sites swept**, beyond the two production call sites above:
`test_mirror_manifest.py` (three `RemoteMirrorNamespaceManifest(...)` call
sites, now passing the already-imported `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION`
production constant, since this file already imported it for an unrelated
assertion), `test_mirror_manifest_digest_identity.py` (two call sites, given a
new local `_MANIFEST_SCHEMA_VERSION_UNDER_TEST` fixture constant rather than
importing the production constant, following the precedent set by `S158`: the
fixture pins the shape under test and claims nothing about what production
stamps), and `test_google_drive_live.py` (one call site, a live-gated test
given a bare `manifest_schema_version=1` literal since it does not otherwise
couple to the production constant).

**Detector-table edit needing routing (not made here):** all three standing
entries in `STANDING_LITERAL_VERSION_DECLARATIONS`
(`src/cadrumo/core/tests/test_persisted_version_single_declaration.py`) that
name these sites are now stale -- confirmed by running the detector, which
fails `test_every_standing_entry_names_a_live_site` naming exactly the three
keys fixed here (`RemoteMirrorNamespaceManifest.manifest_schema_version`,
`ProfileCustodyOwnerReceipt.schema_version`,
`ProfileCustodyHoldEvidence.schema_version`), while
`test_no_new_version_field_authors_its_own_number` passes clean. That test
file is out of this Step's ownership; the three stale entries need deleting
by whoever owns it.

**Enrolment routing needed (not made here):** the newly named
`CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION` constant is ready to enrol as
`PersistedFormatClass.REGENERABLE` in `PERSISTED_FORMATS`
(`src/cadrumo/core/compatibility_lifecycle.py`) with a matching entry in
`VERSIONED_FORMAT_IMPLEMENTATIONS`
(`src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`).
Confirmed by running that gate: it now fails
`test_every_version_constant_is_bound_or_deliberately_excluded`, naming
exactly this one new constant as "accounted for nowhere" and instructing that
it be enrolled with an argued durability class rather than assigned by
proximity -- which is already argued (REGENERABLE, per the closed `S161` ADR)
and only needs its enrolment landed. Both files are outside this Step's
ownership.

**Bite proof**, run from a scratchpad script outside the repository (imports
via the real interpreter, mutates no tracked file):
`manifest_schema_version` and `schema_version` on the two required-field
models both refuse (`ValidationError` naming the field) at direct
construction with the field omitted AND at `model_validate_json` on a payload
with the field stripped out post-hoc; a correctly stamped instance of each
still round-trips byte-for-byte through `model_dump_json` /
`model_validate_json`. For the hold-evidence model, the default is confirmed
to still populate a real value, that value equals the named constant, and the
field's source line is asserted to read the constant BY NAME rather than a
literal. All eleven checks passed.

## Notes

**Verification**, all captured to disk and read back:
- `test_persisted_version_single_declaration.py` (the detector itself,
  before/after; see above) -- 7 passed / 1 failed both times, the 1 failure
  being the stale-table finding, not a regression.
- `src/cadrumo/adapters/outbound/storage/tests` (205 tests, includes the
  google-drive-live module) -- 205 passed on a clean re-run.
- `src/cadrumo/application/user_profile/tests/{test_custody_transactions,
  test_custody_roundtrip,test_custody_restore_atomicity}.py`, run serially
  (`-n0`) after the full user_profile suite hung under parallel workers on
  this share -- 39 passed.
- `test_compatibility_lifecycle.py`, `test_compatibility_lifecycle_gate.py`,
  `test_persisted_format_enrolment_binding.py` -- 33 passed / 1 failed, the 1
  failure being the expected enrolment-routing finding above, not a
  regression.

**Attribution.** The first parallel run of the outbound-storage suite failed
collection tree-wide with `NameError: name 'CoreError' is not defined` inside
`src/cadrumo/application/profile_custody/__init__.py:57-58`, a file this Step
never touches; `git status` showed it modified and uncommitted by a peer
mid-flight, and the error's own text names exactly that possibility. A clean
re-run seconds later passed all 205 tests, confirming the failure was the
peer's in-progress edit settling, not this change. The full
`application/user_profile/tests` package hung past an 8-minute timeout under
the default parallel worker count; per the standing local-execution guidance
this worktree's backing share is known to misbehave under concurrent I/O, so
the three custody-specific test files were re-run serially (`-n0`) instead
and passed clean; the full-package hang was not further pursued as
out-of-scope for this Step's three files.

**No mocks, stubs, skips, xfail, or tautological assertions were used.** The
bite proof runs the real pydantic models and the real
`model_validate_json`/`model_dump_json` round trip against a payload
mutated post-hoc to drop the field, from outside the tracked tree.

This row is ready to be marked complete once the two routing items above
(the stale detector-table entries and the hold-evidence enrolment) are
either landed by their owners or explicitly tracked as follow-ups; neither
blocks the correctness of the three fixes made here.
