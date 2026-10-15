---
tags:
  - '#plan'
  - '#full-suite-repair'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-07-01-verification-reconcile-when-present-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:0c6364314b808beb87fd2be6d19c836dfc1316662a1439ac5978a7f623edf255'
---

# `full-suite-repair` plan

## Description

Approved 2026-10-15. The user explicitly requested running the complete justfile test populations including live tests and fixing all failures. The user further required the publisher Google OAuth client to be a fixed, bundled, non-overridable application identity inherited by every native image.

Repair existing behavior under the accepted verification-reconcile-when-present, application-sign-in, MCP signed-in-profile, provider-settings, Google application identity and canonical environment decisions. No test exclusion, suppression, weakened assertion or increased timeout is authorized. Preserve unrelated edits in this shared worktree.

Current evidence and full command logs are in `.logs/test-repair/`. Read the actual logs and process status before resuming commands. Initial full runs continue while focused repairs are verified; do not represent these moving-tree observations as an immutable all-green checkpoint.

## Steps

- [x] `S01` - Enroll computed casillas and validate published authority; `verification declarations for modelos 303, 308, 322, 369 and 390`.
- [x] `S02` - Compile fixed Google publisher identity into every package launch environment; `native environment contract, build provisioning, runtime settings and identity tests`.
- [ ] `S03` - Repair fixture and tooling contracts exposed by the full suite; `test fixtures, CLI metadata, TUI discovery, localization and protocol assertions`.
- [ ] `S04` - Execute the remaining full offline and live test lanes and verify repairs; `all requested justfile test populations and final review`.

## Parallelization

One agent owns the repairs. Independent command lanes may run concurrently with private run outputs. No delegated agents are authorized.

## Verification

Run product, registry, tooling, Windows, OS-keychain, packaging and applicable external-tool justfile lanes. Run the explicit live lane with process-local opt-ins, using the canonical dotenv bridge; fail rather than skip missing prerequisites. Run scoped Ruff, formatting, types and native CMake verification for the publisher-identity change, then rerun affected populations and report exact exits and prerequisites. Native identity must reject ambient replacements on Windows and POSIX, including inherited invocation profiles.
