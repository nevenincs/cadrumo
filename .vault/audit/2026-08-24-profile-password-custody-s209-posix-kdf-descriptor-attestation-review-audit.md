---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:aeabbffc6d29467045870e8120a43ef80a93d9d223b98d3d663b391b624fa7af'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
  - "[[2026-08-13-profile-password-custody-W03-P06-S209]]"
---
# `profile-password-custody` audit: `S209 POSIX KDF descriptor attestation security review`

## Scope

This independent review audited Step `W03.P06.S209` against the accepted custody roll-up and machine-secret decisions. It inspected the current implementation and tests for pre-ready POSIX descriptor closure, exact parent-side attestation, high-numbered authorized descriptors under the child `RLIMIT_NOFILE`, absence of a broadened allowlist or weaker fallback, preservation of parent-owned PTY descriptors, the narrowed `posix_directory_fd` exception boundary, and the recovery subprocess route into the real CLI main.

The reviewer also ran scoped Ruff and host tests, then independently built an isolated WSL environment and executed the complete integration matrix. Ruff passed. The host selected lane reported 18 passed and one expected POSIX-only skip. The WSL command `pytest -q -n 0 -m integration` over the machine-secret subprocess module reported 70 passed and two expected Windows-only skips in 962.59 seconds.

## Findings

No HIGH or MEDIUM findings remain. The worker closes every descriptor range outside standard streams and the exact request/result pair before emitting readiness. The parent still requires an exact descriptor-set match. Passing the parent `SC_OPEN_MAX` bound before the child lowers `RLIMIT_NOFILE` lets authorized high-numbered descriptors survive and remain explicitly attested while all gaps are closed. No alternate allowlist, in-process path, or supervision fallback was introduced.

The PTY/pipe regression launches the real worker with real inherited descriptors and would expose an extra inherited descriptor in the attestation; the full WSL matrix reaches real KDF supervision and CLI subprocess boundaries. The POSIX recovery test now invokes the exported CLI `main` directly instead of a package module with no executable entrypoint. These tests exercise production behavior and are not tautological.

The `posix_directory_fd` change correctly translates only component-open failures into the custody-domain error; it no longer rewrites unrelated `OSError` exceptions raised by code executing inside the yielded context.

## Recommendations

Approve S209. Retain the full WSL matrix as the platform closure gate and keep the exact parent-side descriptor-set comparison as a non-negotiable custody invariant.
