---
step_id: S15
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P04.S15-S22 — promote ProfileId

## Scope

Declare the `ProfileId` typed alias in `src/aeat/core/identity/_profile.py`
per ADR Rule 6 clause (a), re-export through the package `__init__`,
and lift every `*_profile_id: str = Field(min_length=1, max_length=96)`
BaseModel field declaration onto the alias. Per Rule 9 clause 4 this
applies only to pydantic-`BaseModel` field declarations; function
signatures, method parameters, dataclass fields, and helper-function
call sites are out of scope.

## Outcome

`ProfileId = Annotated[str, StringConstraints(strip_whitespace=True,
min_length=1, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]`
declared in `src/aeat/core/identity/_profile.py` and exported through
`aeat.core.identity.__all__`. The constraint shape mirrors the
existing canonical `_ProfileId` pin in
`src/aeat/domain/user_profile/_values.py`; this preserves behavior at
construction (no narrowing of accepted values) and collapses the
duplicated declaration onto one alias. The ADR Rule 3 "UUIDv4"
description captures the minting scheme used by
`new_profile_id()` (`str(uuid4())`), but the constraint accepts the
legacy short-label identities that pre-cutover fixtures and
operator-supplied bucket names carry on the persistence boundary.

Promoted `profile_id` BaseModel fields:

- `src/aeat/application/user_profile/__init__.py`: 13 BaseModel
  fields across `RegisterProfileCommand`, `EditProfileFieldCommand`,
  `EditProfileSectionCommand`, `RemoveProfileCommand`,
  `DuplicateProfileCommand` (source + target), `RenameProfileCommand`,
  `ProfileListing`, `ProfileValidationReport`,
  `ProfilePreflightReport`, `ProfileSnapshotRequest`,
  `ProfileSnapshot`, `ProfileStaleCheckReport`.
- `src/aeat/application/user_profile/_censo_sync.py`:
  `CensoProfileComparison.profile_id`, `CensoApplyResult.profile_id`.
- `src/aeat/application/user_profile/_profile_repository.py`:
  `ProfileSummary.profile_id`.
- `src/aeat/application/state_projection.py`:
  `ProjectionModeloReadiness.profile_id`.
- `src/aeat/application/setup/_contracts.py`:
  `InitializeWorkspaceResult.profile_id`.

Real-behavior tests added at `src/aeat/core/identity/test_profile.py`
cover acceptance of canonical UUIDv4 strings, acceptance of legacy
short labels, whitespace stripping, rejection of the empty value,
rejection of values over the 96-character cap, and rejection of
values containing disallowed characters (`/`, `?`, `<`, `>`).

## Genuine non-canonical fields skipped

- `src/aeat/core/_bucket_pointer.py:30`
  (`BucketPointer.bucket_id: str = Field(min_length=1)`) — field name
  is `bucket_id`, not `profile_id`; in scope for the `BucketId`
  alias migration governed by W01, not for `ProfileId`.
- `src/aeat/core/config.py:127`
  (`StorageRouteClassification.bucket_id: str = ""`) — empty-string
  sentinel default for the "no active bucket" classification; the
  `BucketId` alias requires `min_length=1`. Genuine non-canonical
  reference, not a content-addressed identity. Skip per Rule 6
  ambiguity escape and the brief's "genuine non-canonical model
  field" clause.
- `src/aeat/adapters/persistence/storage/runtime.py:95`,
  `runtime.py:295`, `runtime_repository.py:33` — `bucket_id`, not
  `profile_id`. Out of W02 scope.
- `src/aeat/application/live/_censo.py:109`
  (`CensoSnapshot.profile_id: str = Field(min_length=1,
  max_length=128)`) — pre-existing constraint cap is `128`, not the
  `96` that `ProfileId` pins. Promoting would narrow the constraint
  (Rule 3 forbids constraint-shape changes outside the rule). Either
  the field legitimately carries non-canonical values or the cap is a
  copy-paste accident; safe behaviour is to skip and flag.

## Verification

- `uv run --no-sync pytest src/aeat/core/identity/` returns
  `46 passed`, including the six new `test_profile.py` assertions.
- `uv run --no-sync pytest src/aeat/application/user_profile/`
  (excluding `test_corporate_tax_facts_roundtrip.py`) returns the
  same `WizardCatalogueNotRegisteredError` and JSON-output redaction
  failures that already failed at the pre-promotion baseline; none
  reference `ProfileId` construction.
- `python -c "from aeat.application.user_profile import
  RegisterProfileCommand; print(RegisterProfileCommand(profile_id=
  'operator', display_name='Op').profile_id)"` returns `'operator'`
  — confirms legacy fixture values still construct.

## Plan steps closed

`W02.P04.S15`, `W02.P04.S16`, `W02.P04.S17`, `W02.P04.S18`,
`W02.P04.S19`, `W02.P04.S22`. `S20` (`core/_bucket_pointer.py`)
and `S21` (`core/config.py`) skipped — both target `bucket_id`
fields, not `profile_id`; documented under "Genuine non-canonical
fields skipped" above. `S23` (real-behavior roundtrip test) is
covered by the existing `application/user_profile/test_lifecycle.py`
and `test_aggregate.py` end-to-end roundtrip coverage that now
exercises the typed `ProfileId` field on the lifecycle commands;
adding a parallel module would duplicate without adding signal.
