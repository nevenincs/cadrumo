---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b24900aef9f6232aee741de58397e7d4bb2b2b18f81338f72548822aa07d7c47'
step_id: 'S148'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh reconcile the two enrolment gates whose key spaces disagree, adding the four standalone capsule and pointer files to the independent path discovery source rather than to the hand list, and narrowing the namespace pin so it excludes namespaces without excluding a payload grammar that carries its own version constant

## Scope

- `src/cadrumo/tests/test_persisted_format_enrollment.py and src/cadrumo/adapters/persistence/storage/`

## Description

- Re-derived the independent persisted-format discovery gate from the storage path registry, secure-object record declarations, durability inventory, and version-constant binding gate at current HEAD.
- Used `git blame` and `git show` to establish chronology: commit `3851397ab212` added the three capsule file definitions and root pointer on 2026-08-15; commit `511fc1fa876f` replaced both hand lists with production-registry enumeration later that day.
- Ran `uv run --no-sync pytest -q src/cadrumo/tests/test_persisted_format_enrollment.py src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py -k 'artifact or persisted or namespace or discovered'`; current HEAD produced 16 passes and one failure because the later `profile_capsule_archive_payload` declaration was absent from independent discovery.
- Added that independently versioned non-file payload to `_NON_FILE_FORMAT_KEYS`, preserving the distinction between path formats, non-file payload formats, and namespace-declared record grammars.
- Re-ran `uv run --no-sync pytest -q src/cadrumo/tests/test_persisted_format_enrollment.py src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`; all 14 tests passed in 24.90 seconds.
- Ran `uv run --no-sync pytest -q -m integration src/cadrumo/application/user_profile/tests/test_capsule_archive.py -k 'enrolment_is_not_inferable or recovery_wrapper_survives or recovery_slot_is_the_declared_constant_width'`; all three enrolled, unenrolled, and constant-width recovery-slot archive tests passed in 9.02 seconds.
- Ran `uv run --no-sync ruff check src/cadrumo/tests/test_persisted_format_enrollment.py`; Ruff passed.

## Outcome

The original S148 implementation genuinely pre-existed its empty record: the three capsule files and active-profile pointer are discovered from production path definitions, while namespaces themselves remain excluded and their independently versioned record grammars remain included through production declarations. Re-derivation also found and repaired a subsequent regression introduced when `profile_capsule_archive_payload` was enrolled as durable on 2026-08-20 without joining the independent non-file discovery source. The gate and its recovery-bearing archive lanes are green again.

## Notes

The first persisted-format run is retained as failure evidence rather than rewritten as an immediately green verification. `vaultspec-rag` discovery was unavailable because the local client was version 0.4.1 while the running service was 0.4.2; targeted source reads, registry inspection, blame, history, and focused executable gates supplied the grounding instead. No custody bytes, recovery material, or taxpayer data were read or changed.
