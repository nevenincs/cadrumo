---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload

## Scope

- `src/cadrumo/application/tests/test_config_reset_repository.py`

## Description

- Prove atomicity + permissions: a created journal roundtrips exactly, lands under `reset-operations/` outside the buckets tree, leaves no `.tmp` residue, and (on POSIX) carries `0700` directory / `0600` file modes.
- Prove create refuses replacing an existing operation identity, and that the retention-decision and complete-operation invariants reject an unbacked override and mismatched summary counts.
- Prove corruption fails closed: malformed JSON, a payload copied under a different filename id, and a future `schema_version` all raise `ConfigResetJournalCorruptError`.
- Prove exclusion: a non-journal file in the directory is neither listed nor bucket-discovered (`list_profile_buckets` returns empty), and a symlinked journal root redirected into a bucket is refused with no `.json` written into the target.
- Prove fresh-process durability: a new interpreter reloads the exact validated operation, and four concurrent real child-process writers serialize replacement to leave exactly one complete document with no torn JSON and no staged residue.

## Outcome

Real behavior throughout: real temp-dir filesystem, real permission bits, real `subprocess` child interpreters for the reload and concurrency proofs — no mocks, stubs, monkeypatch, skip, or xfail. This suite is the executable evidence that reset journals persist atomically outside target directories with restrictive permissions and refuse corruption, exclusion, and redirection. 11 tests green; ruff clean; collection clean.

## Notes

Landed in commit `11356b4792`; re-verified at HEAD (11 passed, 11s). The POSIX-only permission assertions are guarded by `os.name != "nt"`, matching the repository's documented POSIX-only chmod semantics rather than asserting a Windows ACL guarantee the platform does not make.
