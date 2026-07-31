---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:0776e616f251d30789a9a494b79b4fcd2df839b28aa0656b6bc3079c6ca6d527'
step_id: 'S25'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
  - "[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]"
---

# Author the authenticated live exercise runbook as an exec template covering operator auth prompts, redaction, command order, expected evidence, and blocker recording

## Scope

- `.vault/exec/2026-06-12-live-pull-verification-sweep`

## Description

- Authored the authenticated live-exercise runbook below as the reusable exec
  template for the operator manual sweep (S26). It codifies the operator auth
  prompt handling, the redaction contract, the pull-only command order, the
  expected evidence shape per command, and the blocker-recording rule that keeps
  a live-blocked row open.

## Outcome

Runbook authored. It is grounded in the concrete live attempts already recorded
in the live-auth blocker audit, so the command order and blocker taxonomy match
observed AEAT behaviour.

### Live-exercise runbook (operator-present)

Preconditions:

- Isolated encrypted profile root (never the shared default), file-backed
  secret store, and a process-local `AEAT_SECRET_PASSPHRASE` of at least eight
  characters generated for the run only.
- Active profile whose tax id matches the operator-authenticated AEAT identity.
- `AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_BROWSER_HEADLESS=false` for the Cl@ve
  approval window.

Redaction contract (mandatory):

- Never print or persist raw NIE/NIF, Cl@ve support number, passphrase, session
  token, or `storage_state` bytes into any vault evidence.
- Cite only aggregate shape: row/declaration/capture counts, `failure_mode`,
  diagnostic ids, and boolean status flags.

Command order (pull-only; `pull-all` is forbidden):

1. `config profile create` -> `config auth configure --provider clave_movil`
   (expect `identity_alignment=matches`).
2. `config auth login --provider clave_movil --fresh --reset-lock` — approve the
   Cl@ve request in the app ONLY when the phone code matches the CLI code, inside
   the AEAT window. Expect `authenticated=true`. If `pending_petition_blocked`,
   clear pending Cl@ve requests and retry.
3. `config profile censo pull` -> `show` / `compare` / `apply`.
4. `app live filed list` then `app live filed pull` (single) and
   `app live filed pull --from-year Y --to-year Y --limit N` (bounded bulk).
5. `app live expedientes pull`.
6. `app live notifications pull`.
7. `app live justificante pull` (only when a filed row exists to target) then
   `list` / `view`.
8. `app overview calendar --allow-incomplete` for projection.

Expected evidence per command: a persisted encrypted `snapshot_id` (where
applicable), typed counts, and typed empty/timeout/drift outcomes. A local
calendar projection is never AEAT evidence on its own.

Blocker recording: any command that reaches AEAT auth and times out, is refused
by G313/pending-petition, or returns an empty account state is recorded with its
`failure_mode` and diagnostic id; the corresponding plan row stays OPEN. A
proven-empty account state is recorded as the evidence, never checked as a
positive pull.

## Notes

- This record authors the template only; it does not itself run the manual
  sweep. The manual sweep row S26 and the positive live-backed rows it would feed
  (S10 censo, S11 filed, S19 censo CLI, S27 live projection, S28 curated lane)
  remain carried forward pending an operator Cl@ve session, an account with a
  filed declaration, and a certificate-credential decision.
