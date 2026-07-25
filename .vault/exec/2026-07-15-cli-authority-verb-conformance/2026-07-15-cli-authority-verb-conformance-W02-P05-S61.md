---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S61'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload

## Scope

- `src/cadrumo/application/tests/test_config_reset_repository.py`

## Description

- Prove a created journal roundtrips atomically with restrictive permissions, asserting the directory and file modes on the real filesystem.
- Prove creation refuses an existing operation identity rather than overwriting a live journal.
- Prove concurrent fresh-process writers leave exactly one complete document, exercising real separate processes rather than threads.
- Prove a fresh process reloads the exact journal, establishing the strict save-load-equality roundtrip across a genuine process boundary.
- Prove corrupt and filename-mismatched journals refuse on load, and prove a future schema version is refused as corrupt.
- Prove the retention decision refuses an override when nothing blocks erase.
- Prove a complete operation requires every target deleted and requires exact reconciled summary counts.
- Prove the repository excludes non-journal files from discovery and refuses a linked root redirected into a bucket.

## Outcome

- The journal is proven durable across a genuine process boundary: a fresh process reloads the exact document, which is the property resume depends on and which an in-process assertion could not establish.
- Atomicity is proven under real concurrent processes, so a torn or interleaved journal is excluded rather than assumed impossible.
- Restrictive permissions are proven on the real filesystem for both the directory and the file.
- Corruption refusal is proven across four distinct damage modes: malformed content, filename-to-payload identifier mismatch, unknown future schema version, and link redirection, so a damaged journal cannot silently authorize a deletion.
- Exclusion is proven in both directions: non-journal files are not discovered as operations, and the journal root cannot be redirected into a bucket directory.
- Focused gate green: the retention-floor, delete, and reset-journal suites ran together at `HEAD` with 26 passed and 0 failed in 175.49 seconds, collected count non-zero and explicitly confirmed.
- Landed in commit `11356b4792`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The proofs use the real repository, real files, real permissions, and real subprocesses; no mock, fake, stub, patch, monkeypatch, skip, or xfail is used.
- The schema-version proof exercises the forward-refusal ceiling rather than any backward-compatibility path, consistent with the project's pre-release zero-legacy posture.
