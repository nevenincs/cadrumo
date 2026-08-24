---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:933097b8f6d63fa1e149f977d1aa50f9979a34ca1e098faa61573d47cab39292'
step_id: 'S222'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Re-run the S209 supervised-KDF platform gate without weakening exact descriptor attestation, worker isolation, or fail-closed supervision and persist the Windows, POSIX, and WSL evidence

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Run the native Windows KDF supervision module and complete machine-secret subprocess module sequentially.
- Run the same KDF supervision module and complete machine-secret subprocess module under the retained isolated WSL2 environment.
- Increase only the real profile-create subprocess timeout after mandatory password plus recovery KDF work reproducibly exceeded the former budget under WSL.
- Re-run the formerly timing-out case and the unreduced WSL module, then run scoped Ruff and ty checks.

## Outcome

The complete platform gate passed on both operating systems:

| Platform and lane | Result | Duration |
| --- | --- | ---: |
| Native Windows KDF supervision | 18 passed, 1 POSIX-only skip | 26.66 s |
| Native Windows machine-secret subprocess matrix | 71 passed, 1 POSIX-only skip | 466.49 s |
| WSL2/Linux KDF supervision | 19 passed | 39.17 s |
| WSL2/Linux machine-secret subprocess matrix | 70 passed, 2 Windows-only skips | 1090.34 s |

Exact commands:

- `uv run pytest -q -n 0 src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`
- `uv run pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- `wsl.exe bash -lc "cd /mnt/y/code/aeat-worktrees/main && source /tmp/cadrumo-s209-venv/bin/activate && PYTHONPATH=src pytest -q -n 0 src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py"`
- `wsl.exe bash -lc "cd /mnt/y/code/aeat-worktrees/main && source /tmp/cadrumo-s209-venv/bin/activate && PYTHONPATH=src pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py"`

Scoped Ruff and ty checks on the modified subprocess module passed.

## Notes

The first WSL gate and a focused retry both timed out after 45 seconds in the stdin profile-create case; no descriptor-attestation, custody refusal, or secret-channel diagnostic was emitted. Mandatory creation now performs both password and recovery KDF work, and the same real case completed in 63.11 seconds after its helper-only timeout was raised to 120 seconds. The unreduced WSL rerun then passed. No production KDF, attestation, descriptor, fallback, or skip behavior changed, and no residual failure remains.
