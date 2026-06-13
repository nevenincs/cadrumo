---
tags:
  - '#adr'
  - '#multi-bucket-test-fixture'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-cli-workflow-redesign-adr]]"
  - "[[2026-06-03-bucket-sealed-archive-adr]]"
  - '[[2026-06-04-multi-bucket-test-fixture-research]]'
---

# `multi-bucket-test-fixture` adr: `Multi-bucket test fixture for active-vs-target operator scenarios` | (**status:** `accepted`)

## Problem Statement

The existing `isolated_runtime_profile` test helper at
`src/aeat/tests/secure_sql.py:124` provisions exactly one bucket
with a single active session. Three operator-facing scenarios
require two distinct buckets co-existing in the test runtime:

- **Delete happy-path** (`BucketMaintenanceService.delete` per the
  2026-06-03 composition-pattern ADR). The service's active-bucket
  guard refuses self-deletion by design; testing the soft-tombstone
  + hard-erase composition needs an operator-active bucket distinct
  from the delete target.
- **Bucket export / import round-trip** (per the
  2026-06-03-bucket-sealed-archive-adr). Cross-host migration
  semantics are testable only when the importer's destination
  bucket is distinct from the source bucket carried inside the
  archive header.
- **Profile-switch lifecycle** (existing
  `select_profile_with_lifecycle_span` paths). Tests that assert
  the activation-event emission across a profile switch need at
  least two profiles to switch between.

Today these scenarios are tested either with mocked active-bucket
resolution (which the test-discipline rules forbid) or are deferred
behind comments referencing this gap. This ADR locks the contract
for a multi-bucket fixture that lands once.

## Considerations

Two design dimensions: how the secondary bucket's master key
material is provisioned, and how the active-session pointer is
managed.

### Master key material

Three options for the secondary bucket's KEK / DEK:

1. **Shared test KEK / DEK across both buckets.** Today
   `isolated_runtime_profile` uses module-level constants
   `_TEST_KEK = b"t" * 32` and `_TEST_DEK = b"r" * 32` for the
   primary bucket session. The secondary bucket reuses the same
   constants. Pro: lowest setup cost. Con: not representative of
   the production scenario where each bucket has its own
   KDF-derived KEK; cross-bucket-key-leak bugs go undetected by
   the fixture.

2. **Distinct test KEK / DEK per bucket.** New constants
   `_TEST_KEK_SECONDARY = b"u" * 32` /
   `_TEST_DEK_SECONDARY = b"s" * 32` derived from a different
   seed. Pro: catches accidental cross-bucket key reuse; matches
   production. Con: the test fixture grows a per-bucket
   session-activation step; tests that switch active profile must
   re-activate under the right session.

3. **Real KDF derivation for both buckets.** Provision a
   `BucketSession` for each bucket using
   `KdfParams.default().to_manifest_params()` and a per-bucket
   passphrase. Pro: maximum fidelity. Con: KDF cost (Argon2id) per
   fixture is non-trivial — the existing single-bucket fixture
   already takes ~1.5s on this codebase; doubling that for every
   multi-bucket test would shift the test-suite wall-clock
   significantly.

### Active-session management

The `aeat_active_profile` settings override is exclusive — only one
profile can be active at a time. The fixture's contract must name
which bucket is active when the test code runs:

A. **Primary active by default, switch via context manager.** The
   fixture yields a `MultiBucketTestRuntime` dataclass carrying
   both buckets; the primary is `aeat_active_profile`. A nested
   context manager `with runtime.switch_to_secondary():` swaps the
   active profile, then restores.
B. **Caller declares which bucket is active.** The fixture takes
   a `primary_bucket_id: str` parameter; that bucket is active.
   The caller never switches; cross-bucket tests use multiple
   fixture invocations.
C. **No default; require explicit activation.** The fixture
   provisions both buckets but leaves `aeat_active_profile`
   unset; the test code activates as needed.

## Constraints

The fixture MUST consume the existing
`isolated_runtime_profile` infrastructure (not duplicate it). The
single-bucket fixture is the canonical setup; the multi-bucket
fixture is a thin composition that provisions a second bucket and
manages session-activation around it.

The fixture MUST NOT couple to peer-active secure-storage code
paths. The fixture's master-key resolution path uses the same
constants and helpers (`EphemeralMasterKeyProvider`,
`BucketSession.open`, `activate_session`) that the single-bucket
fixture uses today. When the secure-storage hardening campaign
(#628) lands new master-key-provider patterns, the fixture's
session-management code follows the same migration.

The fixture MUST work with the existing
`secure_object_repository_for_active_bucket` factory. Tests that
need access to the secondary bucket's secure-object repository
either (a) hold the repository handle the fixture yields directly,
or (b) call the factory after switching active sessions.

## Implementation

This ADR adopts option (2) for master-key material and option (A)
for session-management.

The new fixture lives in `src/aeat/tests/secure_sql.py`:

- A new frozen dataclass `MultiBucketTestRuntime` carries the
  `primary` and `secondary` `TestRuntimeProfile` records, plus the
  `secondary` `BucketSession` handle the `switch_to_secondary`
  context manager activates on entry.
- A new context manager `isolated_two_bucket_runtime` provisions
  both bucket directories + manifests via the existing
  `provision_bucket_directory` + `write_manifest` helpers, opens
  two distinct `BucketSession`s (primary with the existing
  `_TEST_KEK` / `_TEST_DEK` constants, secondary with new
  `_TEST_KEK_SECONDARY` / `_TEST_DEK_SECONDARY` constants),
  activates the primary session, sets `aeat_active_profile` to
  the primary's `bucket_id`, and yields the dataclass. On exit it
  disposes both engines.
- The `switch_to_secondary` context manager re-uses
  `override_settings(aeat_active_profile=secondary_bucket_id)` +
  `activate_session(secondary_session)` for the block duration,
  restoring the primary on exit.

The fixture parameters follow the single-bucket fixture's shape:
`tmp_path`, optional `primary_bucket_id`,
`secondary_bucket_id`, and operator-readable labels for each.

## Rationale

Option (2) catches accidental cross-bucket key reuse without the
Argon2id cost of full KDF derivation (option 3). The
primary-active-by-default + switch-context-manager (option A)
shape lets test bodies stay terse for the common case (operate
against primary; act on secondary through the maintenance service
surface) while preserving an explicit-switch escape hatch for
tests that genuinely need to read secondary's repository
directly.

The fixture stays inside `src/aeat/tests/secure_sql.py` alongside
the single-bucket fixture so future migrations across both
fixtures land in one file. A separate module would split related
test-infra changes across two files for no gain.

## Consequences

Three deferred tests open as new Steps once the fixture lands:

1. `test_delete_removes_bucket_directory_and_emits_bucket_deleted`
   in `bucket_maintenance/test_service_delete.py` — was deferred
   per a TODO comment in the same module.
2. Round-trip happy-path test for the future
   `BucketMaintenanceService.export` / `.import` verb pair: write
   archive from `primary`, import into `secondary`, assert
   manifest digest and content equality.
3. Profile-activation event-emission test asserting that
   `select_profile_with_lifecycle_span(secondary_id)` emits
   `PROFILE_ACTIVATED` carrying the prior-profile pointer.

The fixture is greenfield infrastructure but small (~80 lines of
new test scaffolding). It does not touch peer-active code paths;
the secure-storage hardening campaign #628 can land its
master-key migrations independently and the fixture's
session-management code follows the same pattern the single-bucket
fixture follows today.

## Codification candidates

- **Rule slug:** `test-fixture-no-mock-active-bucket`.
  **Rule:** Tests that need an active-vs-target bucket distinction
  MUST use the `isolated_two_bucket_runtime` fixture, not mock
  the active-bucket resolution (`resolve_active_bucket_id`,
  `secure_object_repository_for_active_bucket`). Mocking the
  active-bucket resolver is the canonical false-positive shape
  for delete-happy-path tests; the fixture's distinct master-key
  material catches the cross-bucket-key-reuse bug class that the
  mock cannot.

  Held until the fixture lands and a second test demonstrates
  the pattern's value.
