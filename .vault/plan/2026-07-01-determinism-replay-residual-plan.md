---
tags:
  - '#plan'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-01-determinism-replay-residual-adr]]'
  - '[[2026-07-01-determinism-replay-residual-research]]'
---

# `determinism-replay-residual` plan

### Phase `P01` - Seam-coverage gate

Static AST gate banning bare datetime.now/utcnow in production; route the corpus_manifest bypass through core.time.now().

- [x] `P01.S01` - Add AST clock-seam conformance gate under core/tests failing on bare datetime.now/utcnow in production (named allowlist for injectable live-AEAT auth/certificate/authenticator/site-health sites); `route corpus_manifest generated_at through core.time.now().; `src/aeat/core/tests/test_clock_seam_usage.py, src/aeat/core/corpus_manifest/__init__.py`.

### Phase `P02` - Surrogate-id determinism

Content-address evidence_id/invoice_id (mirroring derive_transaction_id) so they are stable and trajectory-referenceable; roundtrip + anti-tautology proofs; residual mask only if a single-command opaque leaf remains.

- [x] `P02.S02` - Content-address evidence_id and invoice_id via a clock-free content digest over identifying fields with genuine-duplicate disambiguation; `add roundtrip + anti-tautology proofs; add a ledger-evidence --format json golden scenario under frozen_clock with injected profile_id, adding a residual mask entry only if an opaque single-command leaf remains.; `src/aeat/application/ledger/_evidence.py, src/aeat/application/ledger/_business_operation_invoice.py, src/aeat/core/observability/_golden.py`.

### Phase `P03` - Ordering discipline

Confirm and sort only the output-feeding directory scans; leave membership/aggregation scans alone.

- [x] `P03.S03` - Confirm whether the two ambiguous directory scans feed ordered output; `wrap the output-feeding scans in sorted() at the boundary and leave the membership/aggregation scans alone.; `src/aeat/application/user_profile/_profile_repository.py, src/aeat/entrypoints/cli/_ledger_import_cli.py`.

### Phase `P04` - Coverage axis

Opt-in determinism-conformance axis with per-command byte-identical proof and visible uncovered-gap report; enrol the ledger-add retried-no-op as the first state-transition case via the db_sha256 tier.

- [x] `P04.S04` - Add a determinism-conformance test axis: opt-in enrolment, per-command byte-identical envelope proof under frozen_clock+injected identity against real repositories, and a visible uncovered-gap report; `enrol the ledger-add retried-no-op as the first state-transition case asserting db_sha256 identity after the idempotent second add against a hermetic synthetic var root.; `src/aeat/core/observability/tests/test_determinism_conformance.py`.

## Description

## Steps

## Parallelization

## Verification
