---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:a79247a319ad847ef72894d882aec634a9ffd1fcdc0b71db0229b0bdf8dbae82'
step_id: 'S03'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh implement finite-grid Argon2id calibration and a supervised child with ready-before-secret, framed-DEK-only results, and parent sentinel proof

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Implemented the closed Argon2id parameter grid, resource eligibility, one warm-up plus five-sample median calibration, per-point timeout discard, total-deadline refusal, fixed eligible fallback, and post-success-only upward ratchet proposal.
- Added an operating-system-released cross-process KDF lease derived from the canonical storage authority, with bounded acquisition and owner-death recovery.
- Launched one child for each calibration or unwrap with anonymous framed pipes, allowlisted environment, neutral working directory, ready attestation before any secret, and a 32-byte DEK-only result channel.
- Enforced Windows Job membership, resource-limit readback, kill-on-close cleanup, and handle-list inheritance cleanup; enforced POSIX process groups, hard resource limits, exact descriptor allowlist, and `pass_fds` launch discipline.
- Defined the strict non-publishing sentinel proof seam, deriving AAD and expected plaintext from the envelope profile UUID, DEK epoch, v1 data format, product, and fixed purpose before returning a DEK.
- Added real production-path subprocess tests for calibration selection, sibling-process lease contention and death release, malformed IPC, sentinels, password refusal, environment and working-directory isolation, containment, timeout cleanup, reaping, and ratchet proposals.

## Outcome

The S03 KDF boundary is fail closed: unavailable supervision returns `KDF_SUPERVISION_UNAVAILABLE` without a weaker execution path, and a successful normal unlock releases a DEK only after the child has exited cleanly and the parent has authenticated the strict envelope-bound sentinel. The independent review completed after remediation with no unresolved critical or high finding.

Focused verification completed on Windows:

- `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/custody/tests -q` â€” 24 passed in 36.53 seconds.
- `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/custody` â€” clean.
- `uv run --no-sync ty check --python .venv/Scripts/python.exe src/cadrumo/adapters/persistence/storage/custody` â€” clean.
- `uv run --no-sync basedpyright src/cadrumo/adapters/persistence/storage/custody` â€” 0 errors, 0 warnings.

## Notes

The first independent review raised four high findings covering timed-out calibration selection, process-local leasing, caller-controlled sentinel metadata, and unproven containment. A second review retained two high findings for arbitrary lease roots and incomplete operating-system proof. All findings were remediated and independently re-reviewed before this record was written. POSIX containment assertions are platform-conditioned and source-reviewed on this Windows host; the Windows branch executed real Job Object, handle, containment, deadline, and reaping paths. No product storage, remote state, service state, Git state, or later plan Step was changed.
