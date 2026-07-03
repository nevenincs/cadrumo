---
tags:
  - '#plan'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-01'
tier: L2
related:
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-research]]'
---

# `ledger-add-idempotency` plan

Make manual `ledger add` and non-granting `modelo verify` retry-safe for the autonomous-agent operator: a same-key add is a guarded no-op, genuine duplicates are preserved, and verify reports content-pin instead of accumulating.

## Description

This plan completes the half-built keyed-idempotency hook on manual `ledger add` and
content-pins the `modelo verify` report id, so both single-subject mutating verbs are
retry-safe for the autonomous-agent operator. It implements ADR
`2026-06-30-ledger-add-idempotency-adr` (Option b guarded-idempotent add, Option 1
content-pinned verify report) on the grounding in research
`2026-06-30-ledger-add-idempotency-research`. Manual add gains an existence check modelled
on `create_work_unit`: a same-key add whose content matches the stored row is a true no-op,
a same-key add whose content differs is an instructive conflict refusal, and the keyless
path stays append-only so two genuine identical same-day movements both persist. Manual rows
additionally gain the content-only import fingerprint so they join the existing non-blocking
likely-duplicate advisory. The verify report id is pinned to the verification outcome
(revision, completeness status, findings, verified_by) and drops `run_at` from identity, so a
non-granting retry upserts in place instead of accumulating. Both identities become clock-free,
advancing the separate determinism work. No back-migration is performed per
`no-legacy-compatibility`; the new identity and fingerprint are stamped on write only.

## Steps

### Phase `P01` - Manual add guarded-idempotent no-op and conflict refusal

Complete the half-built keyed-idempotency hook so a same-key retry is a true no-op and a same-key/different-content call refuses, modelled on create_work_unit.

- [x] `P01.S01` - Add an existence check in create_manual_transaction so a same-key add whose content matches the stored row returns the existing-row quintet as a no-op, emitting no second LEDGER_TRANSACTION_CREATED event, leaving created_at and modified_at unchanged, and skipping evidence re-verification, modelled on create_work_unit; `src/aeat/application/ledger/_actions_manual.py`.
- [x] `P01.S02` - Raise an instructive localised conflict error when a stored row exists for the same idempotency key but the command content differs, naming the conflicting field set; `src/aeat/application/ledger/_actions_manual.py`.
- [x] `P01.S03` - Signal the no-op structurally on the result by returning the existing-row quintet with empty bucket_event_ids, preserving the uniform ledger mutation quintet shape; `src/aeat/application/ledger/_actions_common.py`.
- [x] `P01.S04` - Surface the duplicate no-op outcome as an info Notice on the ledger add envelope through the typed notice channel, never as a bespoke result field; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `P02` - Keyless append preservation and content-fingerprint advisory

Keep the keyless path append-only so two genuine identical same-day movements both persist, and stamp the content-only import fingerprint on manual rows so they join the existing non-blocking likely-duplicate advisory.

- [x] `P02.S05` - Stamp the content-only import fingerprint from derive_import_fingerprint onto manual rows at creation time, replacing the current import_fingerprint=None, without folding any timestamp; `src/aeat/application/ledger/_actions_manual.py`.
- [x] `P02.S06` - Confirm the keyless add path remains append-only so two genuine identical same-day movements both persist as distinct rows, and add a regression that locks this behaviour; `src/aeat/application/ledger/tests/`.
- [x] `P02.S07` - Wire manual rows into the existing day-key likely-duplicate advisory so a probable manual duplicate warns non-blockingly and never blocks a genuine movement; `src/aeat/application/ledger/_actions_import.py`.

### Phase `P03` - Verify report content-pinned identity

Pin the verification report id to the verification outcome and drop run_at from identity so non-granting retries upsert in place instead of accumulating.

- [x] `P03.S08` - Change derive_verification_report_id to fold the verification outcome of calculation_revision_id, completeness_status, the findings tuple, and verified_by, and drop run_at from the identity; `src/aeat/domain/modelos/_verification_report.py`.
- [x] `P03.S09` - Update the VerificationReport model validator to re-check the new outcome-pinned id derivation and retain run_at as a non-identity last-seen body field; `src/aeat/domain/modelos/_verification_report.py`.
- [x] `P03.S10` - Confirm verify_modelo_revision upserts the outcome-pinned report in place so a non-granting retry collapses to one report while the granting path stays self-limiting; `src/aeat/application/modelo/_verification_actions.py`.

### Phase `P04` - Agent-harness and CLI idempotency-key contract

Make the agent harness and CLI surface state that a stable idempotency key is required per logical add and the keyless path is append-only.

- [x] `P04.S11` - Update the --idempotency-key CLI help text through the locale CLI to state that a stable key is required per logical add and the keyless path is append-only; `src/aeat/locales/`.
- [x] `P04.S12` - Update the agent-harness ledger persona or skill instruction to mandate passing a stable idempotency key on every ledger add, citing only the live CLI surface; `src/aeat/_data/agent/`.

### Phase `P05` - Real-behaviour idempotency, roundtrip, and gate verification

Prove the retry-safety and genuine-duplicate-preservation contracts against real repositories with no mocks, plus roundtrip and anti-tautology proofs and the focused conformance gates.

- [x] `P05.S13` - Add a real-repository idempotency test proving a retried keyed add yields one row, one creation event, an unchanged created_at, and a no-op notice; `src/aeat/application/ledger/tests/`.
- [x] `P05.S14` - Add a test proving a same-key add with differing content raises the instructive conflict error; `src/aeat/application/ledger/tests/`.
- [x] `P05.S15` - Add a test proving a deliberate duplicate stays possible via the keyless path and via a distinct idempotency key, both yielding two distinct rows; `src/aeat/application/ledger/tests/`.
- [x] `P05.S16` - Add a strict Transaction save-load-equality roundtrip plus anti-tautology proof with the content fingerprint stamp populated non-default; `src/aeat/application/ledger/tests/`.
- [x] `P05.S17` - Add a test proving two non-granting verify retries with identical findings collapse to one report while a changed-finding re-verify produces a distinct report; `src/aeat/application/modelo/tests/`.
- [x] `P05.S18` - Add a strict VerificationReport save-load-equality roundtrip plus anti-tautology proof with run_at populated non-default and the outcome-pinned id enforced; `src/aeat/domain/modelos/tests/`.
- [x] `P05.S19` - Run the focused gates clean: pytest collect-only, the ledger and modelo-verify suites, JSON schema and notice conformance, documented-command and harness-surface conformance, plus lint and type checks; `src/aeat/`.

### Phase `P06` - Filing-record idempotent re-file

Content-pin the filing record id to the filing outcome and make a re-file of an already-presentado revision a clean idempotent no-op, mirroring the verify-report decision, while keeping the not-verified case a hard refusal.

- [x] `P06.S20` - Content-pin derive_filing_record_id to the filing outcome of work_unit_id, calculation_revision_id, filed_by, and member_nif, dropping filed_at from the identity while retaining filed_at as a non-identity last-seen body field, and update the ModeloRecord model validator to re-check the outcome-pinned id; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `P06.S21` - Upgrade the re-file of an already-PRESENTADO revision from the hard CalculationRevisionStateError to a clean idempotent no-op that returns the existing VIGENTE filing record without emitting a duplicate filing record or lifecycle event, keeping the not-VERIFICADO_COMPLETO case a hard refusal; `src/aeat/application/modelo/_filing_actions.py`.
- [x] `P06.S22` - Surface the idempotent re-file no-op outcome as an info Notice on the modelo file envelope through the typed notice channel, never as a bespoke result field; `src/aeat/entrypoints/cli/_modelo_filing_cli.py`.
- [x] `P06.S23` - Add real-repository tests proving a retried file of a PRESENTADO revision returns the existing record as a no-op with no duplicate record or event while a not-yet-verified file still hard-refuses; `src/aeat/application/modelo/tests/`.
- [x] `P06.S24` - Add a strict ModeloRecord save-load-equality roundtrip plus anti-tautology proof with filed_at populated non-default and the outcome-pinned id enforced by the model validator; `src/aeat/domain/modelos/tests/`.

## Parallelization

P01 lands first: the guarded no-op is the core behaviour every later step depends on. After
P01, P02 (keyless append preservation plus the fingerprint advisory) and P03 (verify report
content-pin) touch disjoint files and may run in parallel. P04 (the agent-harness and CLI
idempotency-key contract) depends on P01's final verb behaviour and may run alongside P03.
P05 (tests and gates) runs last, after P01-P04 land. Within P05, the ledger tests (S13-S16)
and the verify tests (S17-S18) are independent; the focused gate sweep (S19) runs last, after
every other step is closed.

## Verification

The plan is complete when every Step is closed and the following checks pass:

- A retried keyed `aeat app ledger add` produces exactly one stored row, exactly one
  `LEDGER_TRANSACTION_CREATED` bucket event, an unchanged `created_at`, and an info no-op
  Notice with empty `bucket_event_ids` (real-repository test, no mocks).
- A same-key add whose content differs raises the instructive localised conflict error.
- A deliberate duplicate stays expressible via the keyless path and via a distinct
  idempotency key, each yielding two distinct rows.
- A strict `Transaction` save-load-equality roundtrip and anti-tautology proof pass with the
  content fingerprint stamp populated non-default.
- Two non-granting `modelo verify` retries with identical findings collapse to one persisted
  report, while a changed-finding re-verify produces a distinct report; the granting path
  stays self-limiting.
- A strict `VerificationReport` save-load-equality roundtrip and anti-tautology proof pass
  with `run_at` populated non-default and the outcome-pinned id enforced by the model validator.
- The mutation quintet, positional-id, and amount-magnitude/direction contracts are unchanged
  (`ledger-mutation-returns-uniform-quintet`, `cli-single-subject-id-is-positional`,
  `ledger-amount-is-absolute-direction-is-authority`).
- The focused gates are green: pytest collect-only, the ledger and modelo-verify suites, JSON
  schema and notice conformance, documented-command and harness-surface conformance, lint, and
  type checks.
