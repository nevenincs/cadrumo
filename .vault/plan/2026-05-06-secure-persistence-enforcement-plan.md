---
tags:
  - '#plan'
  - '#secure-persistence-enforcement'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-secure-persistence-enforcement-research]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-research]]'
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-plan]]'
  - '[[secure-persistence-foundation.index]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-wave7-audit]]'
  - '[[2026-05-05-codebase-sanitization-audit]]'
---



# `secure-persistence-enforcement` `continuous-audit-rollout` plan

Make the encrypted SQL secure-object backend the continuously enforced
boundary for governed sensitive persistence.

The rollout preserves explicit exceptions for `OPERATIONAL` `.env`
configuration and explicit user-directed exports. It also resolves the pending
policy status of redacted `DIAGNOSTIC` observability filesystem artifacts.

## Proposed Changes

The secure persistence hardening work should move from one-off migrations to
continuous enforcement. The policy test becomes the central programmatic guard
against sensitive repositories reintroducing direct file writes, temporary
file materialization, or older envelope helpers.

The plan extends that guard until every governed sensitive production writer
either uses `SecureObjectRepository`, is covered by an accepted exception, or
is explicitly documented as outside the secure persistence boundary.

## Tasks

- Phase 1: Normalize Enforcement Scope
  1. Confirm the governed sensitivity classes for persistence enforcement:
     `SECRET`, `SESSION`, `IDENTITY`, `FINANCIAL`, `AUDIT`, `CACHE`,
     `CORPUS`, and in-scope `DIAGNOSTIC`.
  1. Record `OPERATIONAL` `.env` configuration as a controlled exception,
     limited to fixed owned keys and non-secret password variable naming.
  1. Record explicit user-directed exports as boundary crossings outside
     normal repository persistence.
  1. Treat service-account file paths as loader input sources only when no
     secure cached payload exists.
  1. Treat `store_dir`, `path`, `envelope_path`, `lock_target`, and
     `db://secure_objects/...` in migrated repositories as logical identifiers
     or compatibility markers.

- Phase 2: Expand Policy-Test Coverage
  1. Extend `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
     to cover all governed sensitive production writers identified by current
     audits.
  1. Add `src/aeat/core/observability/_store.py` to explicit triage, either
     as covered, excepted, or deferred pending the `DIAGNOSTIC` observability
     decision.
  1. Review general locale and corpus writers for `CORPUS`, `OPERATIONAL`, or
     non-sensitive classification.
  1. Keep the canary focused on real production write surfaces.
  1. Continue forbidding direct sensitive use of `write_text`, `write_bytes`,
     write or append mode `open()`, `NamedTemporaryFile`, `mkstemp`,
     `save_envelope`, `save_encrypted_envelope`, and
     `load_encrypted_envelope`.

- Phase 3: Continuous Audits
  1. Run recurring source audits for direct file writes, temporary file
     materialization, storage-envelope helper usage, and compatibility marker
     misuse.
  1. Classify each finding by sensitivity class and persistence role.
  1. Separate normal repository persistence from explicit export behavior.
  1. Separate loader input paths from persistence outputs.
  1. Update the finding ledger when live code diverges from older vault
     artifacts.

- Phase 4: Remaining Write-Surface Triage
  1. Triage `core/observability/_store.py` as redacted `DIAGNOSTIC`
     filesystem persistence.
  1. Decide whether redacted `trace.json` and `events.jsonl` artifacts remain
     permitted, move to secure objects, or split by diagnostic subtype.
  1. Triage general locale and corpus writers against `CORPUS`, `OPERATIONAL`,
     and non-sensitive classifications.
  1. Confirm that migrated profile, financial, filing, audit, workflow,
     Google credential, LLM cache, usage, browser session, Cl@ve Movil, and
     user CLI repositories continue to route through `SecureObjectRepository`.
  1. Verify that setup profile persistence rejects real NIF writes against
     unsecured deterministic backends.

- Phase 5: Verification
  1. Run the sensitive-persistence policy test after every enforcement-scope
     change.
  1. Add non-tautological tests for newly covered surfaces that exercise real
     behavior where practical.
  1. Verify that secure-object reads are gated by `expected_class` and
     `max_supported_version`.
  1. Verify that redacted `DIAGNOSTIC` cache reads remain intentionally lossy.
  1. Verify that `.env` writes contain only allowed `OPERATIONAL` keys and do
     not materialize password values.
  1. Verify that service-account fallback paths are input-only and do not
     reintroduce unsecured helper persistence.
  1. Verify that explicit user-directed exports are documented and
     distinguishable from normal persistence paths.

## Parallelization

Policy-test expansion and write-surface classification can run in parallel
when write scopes are separated. Observability triage should remain isolated
because it may require a follow-up decision on redacted diagnostic artifacts.

Repository migration tasks can be parallelized by bounded surface only:
profile, Google credential material, LLM diagnostics, auth session state,
financial domain, filing domain, workflow state, and observability should not
share write scopes during the same execution wave.

## Verification

Mission success requires a passing policy canary and real behavior tests for
the migrated surfaces. The test suite should prove both positive behavior
and negative leakage properties where practical: logical paths should not be
materialized, payload canaries should not appear in database bytes, and class
or schema-version mismatches should fail on read.

The rollout is complete when all governed sensitive production writers either
use `SecureObjectRepository`, are covered by an explicit accepted exception,
or are documented as outside the secure persistence boundary.

The status of redacted `DIAGNOSTIC` observability filesystem persistence must
be resolved by decision, not left implicit.
