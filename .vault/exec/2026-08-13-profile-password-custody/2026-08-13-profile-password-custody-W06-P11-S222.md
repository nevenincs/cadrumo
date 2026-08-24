---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:46d18501ac91d7ff98db6c6b97362dbcf4594c2ed4581c7d5291cb21350d0070'
step_id: 'S222'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Re-run the S209 supervised-KDF platform gate without weakening exact descriptor attestation, worker isolation, or fail-closed supervision and persist the Windows, POSIX, and WSL evidence

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Replace Windows-only and POSIX-only platform skips with always-collected native-route tests.
- Preserve real Windows inherited-HANDLE/Job Object proof and POSIX inherited-descriptor/PTY proof rather than masking either platform.
- Run the complete KDF supervision and machine-secret subprocess matrices sequentially on native Windows and isolated Ubuntu WSL.
- Run scoped Ruff and ty checks for the complete custody and machine-secret subprocess surfaces.
- Run the canonical skip/xfail inventory and record its one non-S209 carry-forward for the fresh-context close review.

## Outcome

The complete platform gate passed on both operating systems:

| Platform and lane | Result | Duration |
| --- | --- | ---: |
| Native Windows KDF supervision | 19 passed, zero skips | 28.17 s |
| Native Windows machine-secret subprocess matrix | 70 passed, zero skips | 524.11 s |
| WSL2/Linux KDF supervision | 19 passed, zero skips | 35.66 s |
| WSL2/Linux machine-secret subprocess matrix | 70 passed, zero skips | 1192.31 s |

Exact commands:

- `uv run --no-sync pytest -q -n 0 -m unit src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`
- `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- `wsl.exe -d Ubuntu -- bash -lc "cd /mnt/y/code/aeat-worktrees/main && UV_PROJECT_ENVIRONMENT=/home/hello/.cache/cadrumo-s222-wsl uv run --no-sync pytest -q -n 0 -m unit src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py"`
- `wsl.exe -d Ubuntu -- bash -lc "cd /mnt/y/code/aeat-worktrees/main && UV_PROJECT_ENVIRONMENT=/home/hello/.cache/cadrumo-s222-wsl uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py"`

Scoped Ruff and ty checks on the complete custody and machine-secret subprocess surfaces passed. The canonical no-skip inventory reports one remaining external user-profile symlink-construction shortcut, carried to S223 rather than represented as a green global ratchet.

Additional focused evidence: `test_capsule.py` passed 18 tests in 7.53 seconds, and the complete S209-owned platform worktree passed scoped Ruff, ty, and `git diff --check`. Feature-scoped Vaultspec validation passed with every check clean after the execution record, audit, generated feature index, and plan state were reconciled through their owning CLI commands. The independent review passed at current HEAD after the final native Windows and WSL matrix counts were available.

## Notes

The current collection contains no S209-owned skip or xfail marker. Native routing remains real: Windows exercises inherited HANDLE allowlists through the bootstrap and Job Object containment, while POSIX/WSL exercise `pass_fds`, resource limits, process-group isolation, exact descriptor attestation, and inherited-PTY closure before readiness. The independent review found no HIGH or CRITICAL issue. It records one LOW refusal-snapshot coverage gap for S223: session and receipt artifact names are presently excluded from the no-mutation snapshot, so the fresh-context review must ensure those artifacts are explicitly covered.
