---
tags:
  - '#plan'
  - '#runtime-without-service-manager'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-10-03-runtime-manager-architecture-research]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:861091ec77ce7c72729518ed8dabd51be55b49cf1fe852f901e5a9daee33bb5f'
---

# `runtime-without-service-manager` plan

Remove runtime management while preserving shared runtime hosting, authentication, custody and worker containment.

## Description

Approved 2026-10-03 under the operator's explicit instruction to amend all related ADRs, remove runtime health/service management throughout the codebase and defer its design to application bundling, building and provisioning.

2026-10-03-runtime-without-service-manager-adr and the amended MCP runtime/profile-access ADRs govern this work. The exclusion covers installation and registration, global start/stop/status controls, health monitoring, autostart and restart supervision on every platform, including branches in shared modules. It does not remove the runtime executable, verified IPC, handshake/refusals, profile/session administration, operation supervision, safe shutdown or transient worker containment.

Clients connect to an explicitly started runtime until provisioning defines launch policy. This plan introduces no replacement launcher or supervisor. Existing machine registrations are outside repository cleanup. No compatibility shim or unreachable management implementation remains.

## Steps

- [x] `S01` - Apply the operator-authorized exclusion of runtime management to the runtime and profile-access ADRs and reconcile affected open plan scope; `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md, .vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md, .vault/adr/2026-10-03-runtime-without-service-manager-adr.md, affected plan prose and open Steps`.
- [ ] `S02` - Remove manager startup wiring and retain verified connection to an explicitly started runtime; preserve isolated bootstrap, custody and worker containment; `src/cadrumo/adapters/local_runtime/startup.py, runtime_client.py, src/cadrumo/entrypoints/runtime/bootstrap.py, main.py, owning tests`.
- [ ] `S03` - Remove runtime administration and health management from application contracts, transport dispatch, CLI and TUI; preserve profile-session and operation administration and internal safe shutdown; `src/cadrumo/application/runtime/, src/cadrumo/adapters/local_runtime/, src/cadrumo/entrypoints/cli/, src/cadrumo/entrypoints/tui/, owning tests`.
- [x] `S04` - Delete all platform runtime service managers and their exclusive dependencies, settings and tests; preserve transient worker containment and admission observations; `src/cadrumo/adapters/local_runtime/, src/cadrumo/entrypoints/runtime/, owning tests`.
- [ ] `S05` - Remove stale management documentation and locale keys, regenerate CLI references and adapt test-owned runtime lifetimes without OS registration; `src/cadrumo/locales/, docs/, dev/agent_eval/tests/, runtime and frontend tests`.
- [ ] `S06` - Verify no runtime-management implementation remains, run focused runtime and frontend checks with lint/type/import and reference validation, and record integrated review with explicit platform limits; `affected source, tests, generated references, feature audit and ledger`.
- [ ] `S07` - Clarify developer and test-owned runtime lifetimes; verify automatic fixture setup/teardown, run runtime suites with timings and record exact remaining failures.; `runtime ADR, src/cadrumo/tests/README.md, runtime test fixtures and owning suites, audit`.

## Parallelization

One writer integrates this plan. Preserve concurrent worktree changes and re-read affected files before editing. Verify the integrated runtime and frontend behavior after all removals.

## Verification

- Source inspection finds no runtime service registration, health administration or start/stop/status management code, imports, command declarations, UI actions or stale product documentation.
- Missing endpoints return typed unavailability; existing endpoints retain native peer and cohort verification. No connection attempt provisions OS state or starts a process.
- Transport tests preserve correlation, deadlines, cancellation and cleanup; runtime shutdown and worker containment remain intact.
- The CLI has no runtime administration family and the TUI exposes no runtime health or lifecycle controls. Profile/session/grant administration remains available.
- Focused runtime, CLI and TUI tests pass, with lint, format, type/import-boundary, locale and generated-reference checks. Test-owned runtimes are released after each test.
- Record actual platform coverage and unresolved baseline failures. Native Linux/macOS behavior cannot be certified by a Windows run.
