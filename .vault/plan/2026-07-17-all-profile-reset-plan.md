---
tags:
  - '#plan'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-19'
tier: L2
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `all-profile-reset` plan

### Phase `P01` - Deletion assessment and reset ownership

Give bucket maintenance a target-scoped deletion assessment and an operation-owned deletion guarded by a fingerprint.

- [x] `P01.S01` - Add target deletion assessment and reset ownership fields to bucket-maintenance contracts; `src/cadrumo/application/bucket_maintenance/_contracts.py`.
- [x] `P01.S02` - Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion; `src/cadrumo/application/bucket_maintenance/_service.py`.
- [x] `P01.S03` - Define the authoritative deletion-relevant bucket fingerprint for assessment and resume; `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`.
- [x] `P01.S04` - Prove deletion assessment reports real retention blockers without mutating the bucket; `src/cadrumo/application/bucket_maintenance/tests/test_service_retention_floor.py`.
- [x] `P01.S05` - Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence; `src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py`.

### Phase `P02` - Reset journal and durable state

Persist non-secret reset operation state atomically outside target directories so every phase boundary resumes honestly.

- [x] `P02.S06` - Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models; `src/cadrumo/application/_config_reset_models.py`.
- [x] `P02.S07` - Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal; `src/cadrumo/application/_config_reset_repository.py`.
- [x] `P02.S08` - Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload; `src/cadrumo/application/tests/test_config_reset_repository.py`.

### Phase `P03` - Reset orchestration over all targets

Replace scoped reset with start, status, and resume composing the established profile, retention, auth, certificate, and pointer authorities.

- [x] `P03.S09` - Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S10` - Acquire target locks in sorted UUID order and persist every retention decision before mutation; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S11` - Invoke target-scoped auth reset and delete canonical secure-storage certificate secrets before each target deletion without certificate keyring reconciliation or migration; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S12` - Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S13` - Persist deleting ownership before deletion and completion after each irreversible transition; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S14` - Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status; `src/cadrumo/application/config_reset.py`.
- [x] `P03.S15` - Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults; `src/cadrumo/application/tests/test_config_reset.py`.
- [x] `P03.S16` - Prove every reset phase boundary resumes honestly in a fresh child process; `src/cadrumo/application/tests/test_config_reset_recovery.py`.
- [x] `P03.S17` - Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes; `src/cadrumo/application/tests/test_config_reset_concurrency.py`.

### Phase `P04` - Reset and sandbox CLI door

Cut the config reset and sandbox command grammar over to the reset orchestration authority.

- [x] `P04.S18` - Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names; `src/cadrumo/entrypoints/cli/_config/_custody.py`.
- [ ] `P04.S19` - Remove the config profile sandbox use registration and execution path without an alias; `src/cadrumo/entrypoints/cli/_config/_sandbox.py`.
- [x] `P04.S20` - Replace flat scoped reset registration with the config reset command group; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [x] `P04.S21` - Register only reset start, status, and resume with operation, retention, reason, and confirmation options; `src/cadrumo/entrypoints/cli/_config/_reset_cli.py`.
- [ ] `P04.S22` - Prove exact sandbox labels work through switch while sandbox use and bare names are absent; `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`.
- [x] `P04.S23` - Prove switching and strong logout through real persisted custody state; `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`.
- [x] `P04.S24` - Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes; `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`.
- [x] `P04.S25` - Require yes for reset start and resume while keeping status non-destructive; `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`.

### Phase `P05` - Contract migration for the reset family

Move the reset payload schemas, write-policy tokens, locales, help and risk metadata, and generated documentation.

- [x] `P05.S26` - Migrate the reset payload schemas and write-policy tokens to the accepted reset grammar; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `P05.S27` - Migrate the reset family help and risk metadata to the accepted grammar; `src/cadrumo/application/operator_surface/_help.py`.
- [ ] `P05.S28` - Migrate the four locale catalogues for the reset and sandbox families through the locales CLI; `src/cadrumo/locales/en.yml`.
- [ ] `P05.S29` - Regenerate the CLI reference and operator how-to pages for the reset family from the frozen live surface; `docs/reference/commands-and-configuration.md`.
- [ ] `P05.S30` - Prove the removed reset and sandbox spellings are absent from every source and generated surface; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

## Description

Make all-profile reset a single durable, resumable, retention-respecting authority and cut its command grammar over to match. This plan carries the worst outstanding operator-safety defect in the campaign: reset can delete the active bucket and leave a dangling pointer behind, and it can bypass the retention floor. Both are destructive and both are silent.

The accepted authority is one reentrant pointer transaction, with strong profile logout closing resources before clearing the pointer, and all-profile reset composing the established profile, retention, auth, certificate, and pointer authorities rather than reimplementing any of them. Reset does not become a second writer for any state it touches; it invokes the canonical owner for each. The pointer and logout cluster this depends on has already landed.

Reset is replaced by start, status, and resume. State is durable and non-secret, journalled atomically outside the target directories so that a crash at any phase boundary resumes honestly in a fresh process rather than leaving a half-deleted profile. Targets are locked in sorted order to avoid deadlock between concurrent operations, every retention decision is persisted before any mutation, and deleting ownership is recorded before deletion with completion recorded after each irreversible transition. Resume rolls forward: it reacquires locks and rechecks fingerprints and retention rather than assuming its earlier assessment still holds. Status never mutates.

The decision record keeps reset distinct from neighbouring verbs on purpose. Profile logout closes local profile resources and is not destructive; reset is. Sandbox discard removes a selected sandbox; retention prune applies retention-based cleanup. This plan preserves those distinctions.

Four steps below are already landed and carry execution evidence under the originating campaign feature stem, which the rescope record documents. Do not re-execute them.

## Steps

## Parallelization

The deletion-assessment phase and the reset-journal phase touch disjoint files and may run in parallel. The reset-orchestration phase depends on both: it cannot compose an assessment or persist a journal that does not exist yet. The CLI door depends on the orchestration authority. The contract migration runs last, because it regenerates documentation from the frozen live surface and asserts the removed spellings are absent.

Reset composes the auth, certificate, and pointer authorities, so the auth and certificate custody work must be landed before the orchestration phase invokes them; it is, apart from those families' CLI doors, which reset does not call.

The config payload module and the four locale catalogues are shared with peer campaigns and must be serialized rather than co-edited. Route all locale work through the locales CLI.

## Verification

Fresh-process crash-resume suites pass: every reset phase boundary resumes honestly in a real child process, with no phase leaving a target half-deleted, no premature completion record, and no resume that proceeds on a stale fingerprint or a stale retention decision.

The concurrency suite passes against real processes: locks are acquired in sorted order, concurrent writers pause rather than interleave, targets under an active reset are excluded, retention is rechecked on resume, and confirmation is renewed rather than inherited.

Deletion assessment reports real retention blockers without mutating the bucket, and operation-owned deletion rejects a fingerprint mismatch and accepts only journal-proven absence.

Target discovery includes live, tombstoned, and dangling-pointer buckets and excludes cold defaults, so a dangling pointer is reconciled rather than stranded.

Reset grammar conformance passes: only start, status, and resume are registered; start and resume require explicit confirmation while status stays non-destructive; exact sandbox labels resolve through switch while sandbox use and bare names are absent; and the removed reset and sandbox spellings are absent from every source and generated surface.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.
