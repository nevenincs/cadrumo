---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8c5527092395d10bfa882b632272fd20d4c6b78b857a2e76875bfbd7a91460d3'
step_id: 'S33'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-establish the strict roundtrip and anti-tautology proof for the profile-record persistence boundary that the discovery step deleted, populating every defaultable field with a non-default value and proving load refuses a mutated on-disk payload

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

- Read `test_profile_record_persistence_roundtrip.py`, its shared fixture module
  `_profile_record_boundary_support.py`, and the sibling
  `test_profile_record_cross_process_roundtrip.py` in full and adjudicated each
  clause of the row against the code rather than the test names.
- Used `git log --diff-filter=D -S` to locate the proof the discovery step actually
  deleted (`test_repository_roundtrip.py`, removed in `7c062ed17e`, "make the
  custody capsule the sole profile authority") and compared its coverage to what
  exists today.
- Ran the full 11-test suite (roundtrip + cross-process) and captured output.
- Wrote a throwaway pytest plugin outside the repo tree, loaded via `PYTHONPATH`
  and `-p`, that disables the domain model's content-digest self-check
  (`UserProfileRecord._validate_current_record`) at the decode boundary while
  preserving the production exception-wrapping shape, and re-ran the suite to
  confirm the anti-tautology proof genuinely bites.

## Outcome

Row is **satisfied by existing work**; no test code needed to be added or
changed to close it.

Per-clause adjudication of `test_profile_record_persistence_roundtrip.py`:

- **(a) Strict roundtrip, real adapters.** Met. The fixture publishes a real
  capsule through `ProfileCapsuleLifecycle`, encrypts under a real
  `ProfileRecordSession`/DEK, uses a real on-disk SQLite database via
  `profile_custody_secure_object_repository`, and decodes through production
  `UserProfileRecord.model_validate_json`. Nothing mocked or stubbed.
  `test_populated_record_survives_the_encrypted_capsule_boundary_unchanged` and
  `test_replacement_record_survives_the_boundary_with_its_lineage_intact` assert
  full pydantic `==` equality (`loaded == written` / `loaded == replacement`),
  not partial-field or string-shape checks.
- **(b) Every defaultable field populated non-default.** Met.
  `test_every_defaultable_field_is_populated_non_default_across_the_boundary`
  derives the defaultable-field set from `type(record).model_fields` itself
  (`defaultable_fields_at_default` in the shared support module), not a
  hand-picked list, so a newly added field is covered automatically. The two
  fields that cannot honestly carry a non-default at revision one
  (`record_revision`, `previous_record_digest`) are proven via a real CAS
  replacement to revision two rather than excluded silently; the two
  schema-pinned fields (`schema_id`, `schema_version`) are excluded with their
  own dedicated test
  (`test_schema_identity_fields_are_pinned_not_merely_defaulted`) proving the
  exclusion is a genuine model constraint, not a convenience; the two
  clock-defaulted fields are proven by exact reproduction of distinct pinned
  instants instead of inequality.
- **(c) Anti-tautology: on-disk mutation via the real write path.** Met.
  `_rewrite_persisted_payload` decrypts through the real secure-object
  repository, mutates the decoded JSON, and re-encrypts through
  `objects.apply_batch` with the real namespace, object key, write provenance,
  source event id and CAS `expected_revision_id` token — not hand-written
  bytes. `test_load_refuses_a_persisted_payload_with_a_required_field_deleted`
  and `test_load_refuses_a_persisted_payload_with_a_defaultable_field_deleted`
  each assert `ProfileRecordIntegrityError` with a chained `ValidationError`
  cause, the latter asserting the specific "content digest does not match"
  message.

Ran the suite before touching anything:
`uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_profile_record_persistence_roundtrip.py src/cadrumo/application/user_profile/tests/test_profile_record_cross_process_roundtrip.py -v`
— 11 passed in 56.54s. Full output captured to the session scratchpad.

**Bite-proof (the part that actually decides the row).** Wrote a pytest plugin
under the session scratchpad (never committed, loaded only via `PYTHONPATH`/`-p`
against the installed `cadrumo` package, no tracked file touched) that replaces
`cadrumo.application.user_profile._capsule_record._decode_profile_record` with a
version that strips the persisted `content_digest` before validating, so the
model's own `_validate_current_record` re-derives a fresh digest from whatever
survived instead of checking it against the one written at save time — the
literal "loader recomputes instead of refusing" defect class the proof exists to
catch — while preserving the original `ValueError` -> `ProfileRecordIntegrityError`
wrapping shape so unrelated tests do not fail for the wrong reason. Re-ran the
suite under this plugin:
- All four positive/control assertions (equality at revision one and two, the
  full defaultable-field sweep, the schema-pinning proof) still pass, confirming
  the break is scoped and not a blunt sledgehammer.
- `test_load_refuses_a_persisted_payload_with_a_required_field_deleted` still
  passes, correctly, because `profile_id` has no default and pydantic's own
  required-field enforcement is untouched by this specific break.
- `test_load_refuses_a_persisted_payload_with_a_defaultable_field_deleted`
  **goes red**: `assert isinstance(cause, ValidationError)` fails because
  `cause` is `None`. With the digest self-check disabled, the corruption is
  still caught, but by an independent, redundant guard
  (`_assert_event_binding`, which compares the record's digest against the
  immutable value recorded in the append-only bucket-event witness at write
  time) rather than by the mechanism this specific test's docstring and
  assertion claim to prove. The test correctly fails the moment the mechanism
  it names is disabled, proving the assertion is not vacuous — it binds to a
  real, individually-necessary code path, not a redundant one it happens to
  share a false-positive with. No tracked file was ever edited; only an
  external plugin was used, for the duration of one test run.

**Row premise check (discovery-step deletion).** `git log --diff-filter=D` /
`-S` on `src/cadrumo/application/user_profile/tests/` found the row's named
antecedent: `test_repository_roundtrip.py`, deleted in `7c062ed17e3` ("make the
custody capsule the sole profile authority"), which covered TWO persistence
boundaries in one file — `ProfileRecordRepository` (the pre-capsule
`UserProfileRecord`/`UserProfileStatus` shape) and `UserProfileSnapshotRepository`
(the immutable filing-time snapshot, unrelated to the capsule cutover and still
live today). `test_profile_record_persistence_roundtrip.py` restores the first
boundary in full — and exceeds the deleted proof's rigor, since the old file's
fixture used a hand-picked field list rather than a model-field-derived sweep and
had no anti-tautology mutation test at all, only a lifecycle-invariant probe. It
does not restore `UserProfileSnapshotRepository` coverage; that boundary's shape
did not change in the capsule cutover, still has basic roundtrip coverage in
`test_repository.py` (`test_snapshot_round_trip_carries_canonical_hash`,
`test_snapshot_repository_round_trip_requires_its_bound_profile`), and is
outside this row's literal scope ("the profile-record persistence boundary",
singular) — no plan row currently asks for its anti-tautology proof, so this is
recorded here as an open gap rather than silently absorbed or silently ignored.

**Attribution.** The three files
(`test_profile_record_persistence_roundtrip.py`,
`_profile_record_boundary_support.py`,
`test_profile_record_cross_process_roundtrip.py`) were introduced in commit
`82a70a3406` ("registry(m303/m270/m280): continue export layout registry sweep
(round 47)"), a large bundled sweep commit that also touched unrelated registry
TOML, five other steps' exec records, and the plan document itself — but did
NOT check this row (`S33` stayed `[ ]` in that same commit) and left no exec
record naming these files. A hypothesis that agent `S165` authored them, since
the sibling cross-process suite reads as direct follow-through on
`W05.P08.S165`'s cross-process object-key digest investigation, is plausible but
unconfirmed from git history alone (no commit trailer, no exec record); a direct
attribution request sent to `S165` had not answered by the time this record was
written. This record does not claim the work as this agent's own; it closes the
row on the evidence above.

## Notes

No production code or test files were added or modified — the row's own tests
tree ownership was not exercised because the row is satisfied by pre-existing
work. No repo files were touched for the bite-proof; the breaking monkeypatch
lived only in a scratchpad pytest plugin loaded via `-p`/`PYTHONPATH` for the
duration of one test run and was never applied to tracked source.
