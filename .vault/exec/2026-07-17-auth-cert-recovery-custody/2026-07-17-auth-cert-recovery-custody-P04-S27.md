---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:5f19bb934d316818e9b639ae5746c3d407931207e9f4e1177f1d4bb308399654'
step_id: 'S27'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove passphrase change through a real encrypted vault

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`

## Description

Verified against HEAD `8af409cd3f`, no re-implementation needed. The plan step names `test_config.py` as its scope, but the real encrypted-vault round-trip proof lives in `test_config_custody_profile_lifecycle.py::test_config_passphrase_change_round_trips_file_custody`, which is the functionally-matching deliverable:

- Creates a real profile via subprocess `aeat config profile create`.
- Rotates the passphrase via `config passphrase change --secrets-stdin`, asserting exit 0 and that the new value never appears in stdout.
- Re-opens the profile under the rotated passphrase via `config profile show`, proving the encrypted vault is genuinely readable only under the new secret.
- A companion case in the same file proves a wrong-current-passphrase attempt is refused.
- `test_config.py` itself carries the refusal-path companions: `test_passphrase_change_without_interactive_stdin_refuses_instructively` and `test_passphrase_change_refusal_json_stream_parses_cleanly_without_traceback_leak`.

## Outcome

Verified complete, zero production-code or test changes needed. `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py -k passphrase -q -m integration` → `1 passed` (real subprocess CLI execution against a real encrypted secure-object store, no mocks/fakes).

## Notes

Bookkeeping-only closure: this record documents verification, not new implementation. The step's scope file annotation (`test_config.py`) undersells where the primary proof lives; the plan text is left as-is per no-hand-edit-step-text discipline, and this record names the actual verifying test.
