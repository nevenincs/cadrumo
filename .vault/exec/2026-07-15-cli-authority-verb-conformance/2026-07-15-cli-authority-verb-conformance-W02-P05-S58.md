---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S58'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence

## Scope

- `src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py`

## Description

- Prove an operation-owned delete rejects a changed fingerprint without mutating the target, so a bucket modified between assessment and deletion survives the attempt intact.
- Prove an operation-owned delete erases a matching target, establishing the positive path against the same ownership machinery.
- Prove absence requires journal proof and is then idempotently accepted, so a missing directory is tolerated only after the journal confirms a matching deleting marker, and a repeat attempt is a clean no-op.
- Prove a linked bucket root is neither assessed nor deleted, closing the symlink and junction redirection path.
- Prove delete refuses when the confirmation flag is false, refuses the active bucket even when confirmed, and carries a translated message on its refusals.

## Outcome

- Ownership verification is proven to be load-bearing: a fingerprint mismatch aborts before any lifecycle mutation, so the assess-then-mutate window cannot be exploited into an unintended erase.
- Journal-proven absence is proven to mean proven, not assumed: the tolerance path is exercised through the journal rather than a bare existence check, and is proven idempotent on retry.
- Link redirection is proven refused at both assessment and deletion, so neither path can escape the configured bucket directory.
- Confirmation and active-bucket refusals are proven to hold independently of reset ownership, so operation ownership does not weaken the ordinary guards.
- Focused gate green: the retention-floor, delete, and reset-journal suites ran together at `HEAD` with 26 passed and 0 failed in 175.49 seconds, collected count non-zero and explicitly confirmed.
- Landed in commit `11356b4792`, with the deletion path decomposed into named phase helpers in `f764cc53de`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The proofs use real bucket directories, real journals, and the real deletion service; no mock, fake, stub, patch, monkeypatch, skip, or xfail is used.
