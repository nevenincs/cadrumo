---
tags:
  - '#plan'
  - '#full-suite-repair'
date: '2026-10-15'
tier: L1
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:dd5df9abc8f709235d13e59f52de9f1d8f60aa61c1d041221211b0d2a1003791'
related:
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
---

# `full-suite-repair` plan

## Description

Approved 2026-10-15. The user explicitly requested running the complete justfile test populations including live tests and fixing all failures. The user further required the publisher Google OAuth client to be a fixed, bundled, non-overridable application identity inherited by every native image.

Repair existing behavior under the accepted verification-reconcile-when-present, application-sign-in, MCP signed-in-profile, provider-settings, Google application identity and canonical environment decisions. No test exclusion, suppression, weakened assertion or increased timeout is authorized. Preserve unrelated edits in this shared worktree.

Current evidence and full command logs are in `.logs/test-repair/`. Read the actual logs and process status before resuming commands. Initial full runs continue while focused repairs are verified; do not represent these moving-tree observations as an immutable all-green checkpoint.

## Steps

- [ ] `S01` - Enroll computed casillas and validate published authority; `verification declarations for modelos 303, 308, 322, 369 and 390`.
- [x] `S02` - Compile fixed Google publisher identity into every package launch environment; `native environment contract, build provisioning, runtime settings and identity tests`.
- [ ] `S03` - Resolve remaining full-suite failures and rerun supported offline and live lanes; `all requested justfile test populations and verification gates`.

## Parallelization

One agent owns the repairs. Independent command lanes may run concurrently with private run outputs. No delegated agents are authorized.

## Verification

Run product, registry, tooling, Windows, OS-keychain, packaging and applicable external-tool justfile lanes. Run the explicit live lane with process-local opt-ins, using the canonical dotenv bridge; fail rather than skip missing prerequisites. Run scoped Ruff, formatting, types and native CMake verification for the publisher-identity change, then rerun affected populations and report exact exits and prerequisites. Native identity must reject ambient replacements on Windows and POSIX, including inherited invocation profiles.
