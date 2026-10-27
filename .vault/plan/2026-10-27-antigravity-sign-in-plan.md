---
tags:
  - '#plan'
  - '#antigravity-sign-in'
date: '2026-10-27'
tier: L1
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-10-17-single-binary-process-tree-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:f91172baab7520296065c28f0c02e944ab5d0b60298f72eb9393abc6e770adf7'
---

# `antigravity-sign-in` plan

## Description

Approved 2026-10-27

Authorization: the owner's CADRUMO-BRIEF.md explicitly authorizes this app integration in Y:/code/cadrumo-worktrees/tui on feature/tui. Preserve unrelated modifications; no commit, push, reset or cleanup is authorized. Steps are cohesive reviewable changes without commits under this explicit exception.

Implement isolated Antigravity CLI sign-in through supplier GUI capability schema 3, discovered browser-code and helper protocol version 1, preserving Claude browser and Codex browser/device. Do not implement provider OAuth, use the shared OS account, manipulate its keyring or import token contents.

Coverage: accepted 2026-10-13-provider-settings-adr governs S01-S03 service ownership, agent-derived capabilities, private person administration, profile custody and lifecycle. Accepted 2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr governs human-only credential acts and exact-profile boundaries. Accepted 2026-10-17-single-binary-process-tree-adr governs containment and the existing host browser handoff. The supplied method/event extension uses these settled mechanisms; no uncovered costly choice or ADR amendment is required. Proposed desktop-agent-host records are supporting context, not execution authority.

Shared contract: method browser-code, active event authorization_code_required, admin connect_submit_code with attempt_id and existing secret_bytes metadata plus separately framed code bytes, native provider_sign_in_submit_code, frontend ProviderSignIn.submitCode({attemptId, code}). The helper receives version 1 action auth_code with nonempty printable-ASCII code at most 2048 characters and complete JSON line at most 4096 bytes. Submit once to the current owned code-required attempt under exact profile/login generation. Serialize with cancellation and reject stale, duplicate or out-of-state input without echoing it; never replay or restart implicitly.

Preserve the validated browser URL across immediate browser_action to authorization_code_required transition so polling cannot lose it; open once through the established host path on either active event, and withdraw URL on submit/cancel/settlement. Entered code is distinct from display-only user_code and never enters snapshots, persistence, history, diagnostics, logs, telemetry or errors. Clear dialog input on submit/cancel/close/profile change.

Supplier coordination confirmed stable source at Y:/code/cadrumo-agent-worktrees/main, HEAD 82fd029f31c1db60938eb605851932de25a1169d, version 0.1.0, dirty working tree including untracked implementation modules, agy 1.4.8. Package proof requires the actual working-tree payload and manifest identity. Supplier source tests/initiation/cancel do not establish completed app OAuth or packaged parity. Quota is exhausted; retain the required same-profile turn evidence as pending until available.

## Steps

- [x] `S01` - Integrate discovered browser-code capabilities and bounded attempt-owned code submission through private service administration with catalog, protocol, lifecycle and refusal tests; `src/cadrumo_agent_service/adapters/agent_provider_catalog.py, host/auth_protocol.py, host/auth_attempt.py, admin.py, service.py and owning tests`.
- [x] `S02` - Present browser-code sign-in through the verified native command and localized transient dialog, update authored IPC contract and regenerate chrome inputs, and cover native/frontend behavior; `native/application-environment.toml and dev/packaging/native invocation/vector tests, native/desktop/src-tauri provider_settings and registration, frontend shell and ProviderSignInDialog.tsx and dev/providerSettingsFixture.ts and authored IPC contract, service locale catalogues and owning tests`.
- [ ] `S03` - Verify integrated behavior and regressions, build with matching agent working-tree identity, and record actual live/package outcomes and prerequisites before final review; `focused Python/native/frontend checks, native package identity and build, disposable isolated-profile app sign-in and same-profile turn, vault execution and review artifacts`.

## Parallelization

S01 and S02 may execute concurrently against the shared contract. Python owns only src/cadrumo_agent_service and its tests. Desktop owns only native/desktop implementation/tests and authored IPC contract plus related locale catalogs. Workers are not alone and must accommodate concurrent changes without reverting them. Root alone serializes shared plan/ledger/review metadata, owns expensive/stateful checks and package builds, and performs checkpoint logging from worker reports. Workers do not commit or change plan structure.

S03 depends on S01 and S02 and stable integrated inputs. Root may delegate bounded native/tests/provider_auth_smoke.py and narrow owning tests to exercise capability schema/new active event/cancel with two fresh homes and an optional provider filter; this work makes no model call and is separate from the desktop worker's owned files. New smoke-test files are authorized creation work. Root holds the final integrated review and reports any unmet live/package prerequisites.

## Verification

S01: exercise actual capability parser, closed event/order validation, attempt private-input path, authenticated administration, lifecycle and resume. Cover schema 3/browser-code without hardcoding provider support, immediate URL transition, ASCII/2048/4096 bounds, invalid/duplicate/out-of-state/stale/profile-generation refusals, cancel/EOF/timeout cleanup, and prior methods. Run focused owning tests plus configured lint/format/type checks. Doubles only isolate pure unit logic; acceptance uses real components.

S02: native wire/command and production-dialog tests cover opening once on both active events, transient input collection/submission/clearing, close/profile-switch, terminal outcome only success, secret-free errors and Claude/Codex regressions. Update the authored IPC contract directly and regenerate chrome inputs through the owning recipe; discovery found no IPC generator. Run frontend npm run check and npm test and applicable CMake-owned desktop host tests/quality checks.

S03: run focused integrated checks then applicable required just check-code, just check-registry-gate and just test-gate on stable inputs. Reuse shared evidence and separate pre-existing failures from regressions. Build/select the package with confirmed supplier working-tree payload and inspect actual package/source identity. Source tests, fixture UI and smoke initiation are not packaged completed-provider proof.

Required live app evidence: a fresh isolated Antigravity profile completes browser action and person code submission through the private route, provider credential persistence, then a same-profile model turn; a second fresh profile refuses silent account inheritance. Preserve ordinary OS account/keyring and never inspect/copy tokens. Do not rerun paid probes against exhausted quota. If person code entry/account/quota is unavailable, leave S03 open and report the exact prerequisite and existing source/build evidence.

Verify entered codes and authorization URLs do not enter persistent app state or diagnostics; only the bounded active URL handoff is allowed. Confirm Cadrumo main and the supplier source checkout were untouched by app implementation. Report changed files, exact commands/results, package/source identity and blockers. Completion requires all Steps closed by owning verbs and integrated vaultspec-code-review passing. No commit/push is authorized.
