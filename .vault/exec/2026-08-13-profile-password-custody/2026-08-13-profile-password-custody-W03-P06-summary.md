---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6c83d903b133163938f2b44cdb9e5bdc23a971c6682bc8716f96997652cfa386'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` `W03.P06` summary

The 36 CLI and TUI authority steps are complete. The phase exposes the accepted profile lifecycle through canonical operator verbs, explicit machine-secret channels, truthful status and recovery surfaces, and strict profile-session preconditions. Its final POSIX closure removes inherited host descriptors from the supervised KDF worker before readiness and proves the complete machine-secret subprocess matrix under WSL.

- Modified: `src/cadrumo/entrypoints/cli/` command specifications, dispatch, custody handlers, machine-secret transport, generated projections, and tests.
- Modified: `src/cadrumo/adapters/inbound/tui/` profile login and recovery-enrollment surfaces and tests.
- Modified: `src/cadrumo/adapters/persistence/storage/custody/` KDF supervision, attestation, POSIX filesystem anchoring, and tests.
- Modified: `src/cadrumo/application/user_profile/`, `src/cadrumo/application/wizard/`, operator documentation, and four locale catalogues where individual steps settled lifecycle and recovery behavior.

## Description

The phase reconciled the registered command tree with operator help, retired stale bootstrap exemptions and obsolete profile-creation assumptions, restored canonical profile actions, moved scalar credentials to bounded stdin or inherited-descriptor channels, required recovery enrollment and verification at creation, and made setup and custody refusals visible through typed outcomes. It also repaired profile-fact event taxonomy, incomplete-setup handling, session retirement, and operator guidance identified while the command surface was exercised.

Final S209 verification retained exact parent descriptor validation, ready-before-secret ordering, `pass_fds`, hard POSIX resource limits, process-group containment, and fail-closed supervision. A real worker inherited extra PTY and pipe descriptors, shed every unauthorized descriptor before readiness, attested only standard streams and its request/result pipes, and left the parent descriptors parent-owned. The full sequential WSL integration module passed 70 applicable cases with two expected Windows-only skips; an independent reviewer reproduced the same 70-pass result and reported no HIGH or MEDIUM findings.
