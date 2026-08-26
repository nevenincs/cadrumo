---
generated: true
tags:
  - '#index'
  - '#ledger-add-idempotency'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b59ee8049c9fd76b55aafc5f086832fd87126d8e1ec4582b65d99f5481c872f1'
related:
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-plan]]'
  - '[[2026-06-30-ledger-add-idempotency-research]]'
  - '[[2026-07-01-ledger-add-idempotency-audit]]'
---

# `ledger-add-idempotency` feature index

Auto-generated index of all documents tagged with `#ledger-add-idempotency`.

## Documents

### adr

- `2026-06-30-ledger-add-idempotency-adr` - `ledger-add-idempotency` adr: `manual ledger add idempotency and verify-report retry shape` | (**status:** `accepted`)

### audit

- `2026-07-01-ledger-add-idempotency-audit` - `ledger-add-idempotency` audit: `ledger-add-idempotency close honesty review`

### exec

- `2026-06-30-ledger-add-idempotency-P01-S01` - Add an existence check in create_manual_transaction so a same-key add whose content matches the stored row returns the existing-row quintet as a no-op, emitting no second LEDGER_TRANSACTION_CREATED event, leaving created_at and modified_at unchanged, and skipping evidence re-verification, modelled on create_work_unit
- `2026-06-30-ledger-add-idempotency-P01-S02` - Raise an instructive localised conflict error when a stored row exists for the same idempotency key but the command content differs, naming the conflicting field set
- `2026-06-30-ledger-add-idempotency-P01-S03` - Signal the no-op structurally on the result by returning the existing-row quintet with empty bucket_event_ids, preserving the uniform ledger mutation quintet shape
- `2026-06-30-ledger-add-idempotency-P01-S04` - Surface the duplicate no-op outcome as an info Notice on the ledger add envelope through the typed notice channel, never as a bespoke result field
- `2026-06-30-ledger-add-idempotency-P02-S05` - Stamp the content-only import fingerprint from derive_import_fingerprint onto manual rows at creation time, replacing the current import_fingerprint=None, without folding any timestamp
- `2026-06-30-ledger-add-idempotency-P02-S06` - Confirm the keyless add path remains append-only so two genuine identical same-day movements both persist as distinct rows, and add a regression that locks this behaviour
- `2026-06-30-ledger-add-idempotency-P02-S07` - Wire manual rows into the existing day-key likely-duplicate advisory so a probable manual duplicate warns non-blockingly and never blocks a genuine movement
- `2026-06-30-ledger-add-idempotency-P03-S08` - Change derive_verification_report_id to fold the verification outcome of calculation_revision_id, completeness_status, the findings tuple, and verified_by, and drop run_at from the identity
- `2026-06-30-ledger-add-idempotency-P03-S09` - Update the VerificationReport model validator to re-check the new outcome-pinned id derivation and retain run_at as a non-identity last-seen body field
- `2026-06-30-ledger-add-idempotency-P03-S10` - Confirm verify_modelo_revision upserts the outcome-pinned report in place so a non-granting retry collapses to one report while the granting path stays self-limiting
- `2026-06-30-ledger-add-idempotency-P04-S11` - Update the --idempotency-key CLI help text through the locale CLI to state that a stable key is required per logical add and the keyless path is append-only
- `2026-06-30-ledger-add-idempotency-P04-S12` - Update the agent-harness ledger persona or skill instruction to mandate passing a stable idempotency key on every ledger add, citing only the live CLI surface
- `2026-06-30-ledger-add-idempotency-P05-S13` - Add a real-repository idempotency test proving a retried keyed add yields one row, one creation event, an unchanged created_at, and a no-op notice
- `2026-06-30-ledger-add-idempotency-P05-S14` - Add a test proving a same-key add with differing content raises the instructive conflict error
- `2026-06-30-ledger-add-idempotency-P05-S15` - Add a test proving a deliberate duplicate stays possible via the keyless path and via a distinct idempotency key, both yielding two distinct rows
- `2026-06-30-ledger-add-idempotency-P05-S16` - Add a strict Transaction save-load-equality roundtrip plus anti-tautology proof with the content fingerprint stamp populated non-default
- `2026-06-30-ledger-add-idempotency-P05-S17` - Add a test proving two non-granting verify retries with identical findings collapse to one report while a changed-finding re-verify produces a distinct report
- `2026-06-30-ledger-add-idempotency-P05-S18` - Add a strict VerificationReport save-load-equality roundtrip plus anti-tautology proof with run_at populated non-default and the outcome-pinned id enforced
- `2026-06-30-ledger-add-idempotency-P06-S20` - Content-pin derive_filing_record_id to the filing outcome of work_unit_id, calculation_revision_id, filed_by, and member_nif, dropping filed_at from the identity while retaining filed_at as a non-identity last-seen body field, and update the ModeloRecord model validator to re-check the outcome-pinned id
- `2026-06-30-ledger-add-idempotency-P06-S21` - Upgrade the re-file of an already-PRESENTADO revision from the hard CalculationRevisionStateError to a clean idempotent no-op that returns the existing VIGENTE filing record without emitting a duplicate filing record or lifecycle event, keeping the not-VERIFICADO_COMPLETO case a hard refusal
- `2026-06-30-ledger-add-idempotency-P06-S22` - Surface the idempotent re-file no-op outcome as an info Notice on the modelo file envelope through the typed notice channel, never as a bespoke result field
- `2026-06-30-ledger-add-idempotency-P06-S23` - Add real-repository tests proving a retried file of a PRESENTADO revision returns the existing record as a no-op with no duplicate record or event while a not-yet-verified file still hard-refuses
- `2026-06-30-ledger-add-idempotency-P06-S24` - Add a strict ModeloRecord save-load-equality roundtrip plus anti-tautology proof with filed_at populated non-default and the outcome-pinned id enforced by the model validator
- `2026-06-30-ledger-add-idempotency-P05-S19` - Run the focused gates clean: pytest collect-only, the ledger and modelo-verify suites, JSON schema and notice conformance, documented-command and harness-surface conformance, plus lint and type checks

### plan

- `2026-06-30-ledger-add-idempotency-plan` - `ledger-add-idempotency` plan

### research

- `2026-06-30-ledger-add-idempotency-research` - `ledger-add-idempotency` research: `manual ledger add idempotency and verify-report retry shape`
