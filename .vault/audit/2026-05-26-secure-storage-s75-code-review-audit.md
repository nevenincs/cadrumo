---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W11-P19-S75]]'
---



# `secure-storage-production-hardening` Code Review

S75-001 | HIGH | RESOLVED | Commit self-containment failed before repair

The S75 review found committed master-key tests using `allow_bucket_dek_enrollment` while the committed production activation signature lacked that argument. The repair commits the production explicit-provisioning and per-bucket DEK activation implementation that the tests exercise, restoring the step's self-contained testability.

S75-002 | MEDIUM | RESOLVED | Skip-gate cleanup missed live keyring skips

The S75 review found `importorskip` and plain `pytest.skip` in the keyring provider test path. The repair converts that roundtrip to the in-process `KeyringClient` implementation already used by the failure-surface tests, removing host-dependent skip gates from the repaired S75 files.

S75-003 | LOW | TRACKED | Passphrase environment tests still use monkeypatch

The passphrase callback tests still exercise `AEAT_SECRET_PASSPHRASE` through `monkeypatch.setenv` and direct environment assertions. This is a real production boundary for the current passphrase callback, but it remains a test-hygiene and settings-centralisation risk. S77 owns guard coverage and disposition for remaining environment and monkeypatch uses.

S75-004 | LOW | RESOLVED | Unreachable assertion in activation-refusal test

The S75 review found an assertion inside a `pytest.raises` activation context where the expected exception occurs during context entry. The repair removes the unreachable assertion and keeps the real behavior check on the persisted staged DEK plus the fail-closed activation path.
