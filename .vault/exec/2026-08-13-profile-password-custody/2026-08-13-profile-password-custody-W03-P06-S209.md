---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:68bdf777867b70ae667798b69c3e26d0ac2ad7e7a2ab2d8d325c2ed117bc0069'
step_id: 'S209'
related:
  - '[[2026-08-13-profile-password-custody-plan]]'
  - '[[2026-08-24-profile-password-custody-s209-posix-kdf-descriptor-attestation-review-audit]]'
---
# Have Terra XHigh reproduce and resolve the WSL supervised-KDF inherited-PTY attestation refusal that prevents the full machine-secret CLI subprocess matrix from reaching dispatch, preserve strict worker isolation without bypasses or weaker fallback, and add a WSL runtime gate proving all five leaf descriptor channels, both restore variants, root authentication, and cross-scope collision semantics

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`
- `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py`
- `src/cadrumo/adapters/persistence/storage/custody/_kdf_attestation.py`
- `src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py`
- `src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py`
- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Reproduce the inherited-PTY refusal through the real WSL worker and full subprocess matrix.
- Close every POSIX descriptor below the parent-observed finite OS bound except standard streams and the two authorized KDF transport descriptors after argument parsing and before ready attestation.
- Preserve exact parent descriptor validation, ready-before-secret ordering, `pass_fds`, process-group containment, hard resource limits, and fail-closed supervision with no fallback.
- Attest authorized transport descriptors even when their inherited numeric values exceed the worker's already-lowered open-file limit.
- Add a real worker regression that deliberately inherits extra PTY and pipe descriptors, proves the ready payload contains only the exact authorized set, and proves the parent retains ownership of its descriptors.
- Narrow the POSIX directory-anchor exception boundary so a caller's expected missing-child result is not misreported as an unsafe anchored directory.
- Route the POSIX recovery-descriptor subprocess case through the real CLI `main()` boundary instead of a package with no module entry point, retaining real `pass_fds` transport and secret-free diagnostics.

## Outcome

The supervised POSIX worker now sheds host-injected descriptors before it attests readiness. The parent still requires exact equality with standard streams plus the request and result descriptors, and no secret is written until that attestation passes. The regression red-tested the prior shape under WSL and passes with extra inheritable PTY and pipe descriptors, including an authorized result descriptor above the post-launch limit.

The exact required sequential WSL command completed with 70 passed and two pre-existing Windows-only platform skips in 919.16 seconds. All applicable Linux cases passed across the five leaf channels, both restore doors, root authentication, descriptor zero, dual-source certificate operation, collision-before-read semantics, cleanup, and non-disclosure. The host KDF module completed with 18 passed and one POSIX-only skip; the WSL KDF module completed with 19 passed. Scoped Ruff and `ty` checks passed.

## Notes

The first full WSL attempt proved the KDF refusal was gone and exposed two previously unreachable POSIX defects. Capsule publication treated a consumer's expected `FileNotFoundError` as an unsafe directory because the directory-anchor context manager caught exceptions thrown through its `yield`; narrowing the catch to component opening preserved no-follow identity checks and allowed the designed absence result. The POSIX recovery case invoked `python -m cadrumo.entrypoints.cli`, but that package has no `__main__`; using a fixed `-c` import of canonical `main()` restored the same real entry boundary used by neighboring subprocess cases.

No mock, patch, fake, runtime fallback, new skip, or weaker attestation was introduced. Whole-file Ruff format checking remains red on unrelated pre-existing formatting in the subprocess module outside this Step's three hunks; scoped Ruff checking and `git diff --check` are clean. Formal review is recorded separately and is required before checkbox closure.
