---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:03e98d5c69fb87f552161a4089fb64ca65173d034cae63258044cc027e92a0a2'
step_id: 'S21'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and implement parsed-dispatch root and leaf source preflight, exact-target login fallback, show validate and history gate convergence, unused-source refusal, target assertions, bounded cleanup, and non-secret persistence warning

## Scope

- `root CLI gate profile target routing session integration and focused tests`

## Description

- Ground parsed dispatch and profile-session authority in the amended ADR, plan, prior execution records, semantic discovery, and exact source searches.
- Preflight root and leaf secret sources from the fully parsed command graph before logging, storage setup, reads, KDF work, session activation, or handler import.
- Converge resume fallback, exact-target show/validate/history routing, manager authentication, and target-specific write guarding onto one session gate.
- Add mutable raw-buffer wiping, bounded descriptor handling, unused-source refusals, non-persistence notices, and a state-free console bootstrap.
- Remove the obsolete root gate and its path/name detection helpers.
- Exercise collision, self-authentication, exact-target fallback, rotation, quickfile, history, manager, and terminal-introspection regressions.

## Outcome

- Root and leaf source collisions refuse unread before a fresh root or log tree is created.
- Exact profile targets resolve once, authenticate against the canonical UUID, assert the serving session, and bind only after proof.
- Root fallback can authenticate keychain-free reads and emits the non-secret session-persistence notice without leaking payloads.
- Every terminal group is explicitly classified as introspection or executable; ancestor groups cannot import or execute handlers before the terminal gate.
- The S19 two-rotation keychain-free contract and the focused S21 dispatch suite pass.

## Notes

- The host OS keychain cannot persist a cross-process acceleration receipt, so the OS-keychain-only unused-source proof skips after verifying the receipt is absent; keychain-free and real-session authorities remain covered separately.
- Shared-branch serialization placed the principal source changes in `d52fdeb068a`; the final scoped test and execution-record follow-up remains separate.
- Final SOL review reported no CRITICAL or HIGH finding; S21 and the linked S19 root-gate contract closed.
- MED follow-up for S22/S18: the non-persistence warning drains through successful `_emit_envelope` rendering, so a handler exception or refusal after login can omit the promised Notice.
- MED follow-up for S22/S18: `_profile_session_gate` still erases secret selections, requested-leaf projections, and callback types to `object`/`Any`; strengthen this security seam with concrete protocol/model types.
