---
tags:
  - '#plan'
  - '#live-verification-session'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-06-12-live-pull-verification-sweep-adr]]'
  - '[[2026-09-24-aeat-live-write-guard-plan]]'
  - '[[2026-10-03-aeat-live-write-guard-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:f4c935ba4ec5b33b340f3b90304a56cd48f9a452e5ed219d03b68450ac7142b9'
---

# `live-verification-session` plan

Prove that the current TUI and CLI can authenticate to AEAT and perform every supported live pull and reconciliation, and every Google Sheets and Drive transfer, against the real services, without any AEAT write.

## Description

Approved 2026-10-03. Basis: the operator reviewed the session design on 2026-10-02 and on 2026-10-03 authorised its implementation in full ("All yours to implement"), including the write-guard browser-level Step that precedes authenticated sessions.

Decision coverage: the accepted `2026-06-12-live-pull-verification-sweep-adr` governs unchanged. This is an authenticated, pull-only, per-surface acceptance pass that records evidence and never writes to AEAT. The earlier sweep plan under that ADR is closed and predates the TUI and the `src/cadrumo` layout, so this plan re-runs acceptance on the current tree rather than reopening it. No new costly decision is involved. Authenticated Steps S04 to S11 depend on `2026-09-24-aeat-live-write-guard-plan` S02, the browser-context request guard, landing first.

Live capability inventory, measured 2026-10-02 from source:

- Authentication: Cl@ve Movil (QR or app_request), Cl@ve Permanente and certificate providers. Sessions are encrypted, per profile and provider, with an 18 minute idle lifetime, and shared by CLI and TUI through `auth.session.acquire`. The numero de soporte is transcribed verbatim without format validation and is used only on the app_request route.
- AEAT reads: filed declarations register and cotejo, expedientes, justificante with CSV verification, IVA compensation wallet, datos censales, notifications, NIF-IVA (no login), GROI, site connectivity. No representation mode; every reader continues in own name only. No live Renta borrador.
- Reconciliation: filing-chain register reconciliation and local versus pulled divergence, IVA wallet versus local 303 recurrence, censo versus profile divergences. Notifications, NIF-IVA and GROI record verdicts only.
- TUI reach: Cl@ve setup in the profile manager, AEAT Sync filed-history pull (which also runs the wallet and notifications stages), notifications list and census review. Wallet alone, NIF-IVA, GROI, notification documents and all Google operations are CLI-only.
- Google: Sheets push (export), Sheets pull and calculate (read-back without local persistence), Drive evidence import into encrypted evidence, encrypted archive push to Drive. OAuth desktop consent requires an interactive terminal.

Known risks to observe rather than assume: the CLI login client waits 120 seconds while the phone wait can also reach 120 seconds; the Cl@ve verification-code banner may surface only in the profile worker; the guard's forbidden token list contains `tgvi`; the product does not read `env/.env`, so CLI runs use `uv run --env-file env/.env` and profile fields take precedence over settings; `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` must stay unset.

Evidence handling: each Step's ledger rows record commands, exit statuses and typed outcome names only. No NIE, NIF, soporte, amounts, notification content or document bytes enter the vault, logs or transcripts.

## Steps

- [ ] `S01` - run the offline preflight: code-sanity gates, no-write and live-write refusal tests, bundled chromium doctor, product config and auth readiness, and the TUI pilot suite, recording each command and exit status; `justfile, src/cadrumo/adapters/outbound/aeat/sede/tests, src/cadrumo/entrypoints/cli/tests, env/.env`.
- [ ] `S02` - configure the active profile for Cl@ve Movil app_request with NIE, numero de soporte and matching identity.tax_id, and prove a mismatched NIE is refused before any browser launches in an isolated profile; `aeat config auth configure, aeat config auth status`.
- [ ] `S03` - exercise the unauthenticated live reads (site connectivity, NIF-IVA against a public VAT number, Cl@ve selector reach and evasion live tests) and prove the launched process is bundled Playwright chromium, never installed Chrome; `aeat config repair connectivity, aeat app live verify nif-iva, src/cadrumo/adapters/outbound/aeat/auth/tests, src/cadrumo/adapters/outbound/aeat/browser/tests`.
- [x] `S12` - build a dev-only verification harness that records method, host and path of every browser-context request (query, body, headers and cookies discarded before write) during the authenticated session, to ground the declared read requests of the accepted write-guard ADR; `dev/acceptance, src/cadrumo/adapters/outbound/aeat/browser/session.py read-only`.
- [ ] `S04` - authenticate with Cl@ve Movil with the operator present through the CLI, prove the verification code reaches the operator, the login completes inside the client timeout, the encrypted session is reused without a second phone prompt, and the TUI AEAT Sync workspace adopts the same session; `aeat config auth login, aeat app tui, src/cadrumo/entrypoints/cli/config/runtime_auth_login.py`.
- [ ] `S05` - Drive censo sync to completion through the CLI and TUI on the same profile runtime; compare fetched driver facts with CLI and TUI views, persisted encrypted database facts and provenance; prove repeat application is idempotent and repair every divergence; `src/cadrumo/entrypoints/cli/config, src/cadrumo/entrypoints/tui/aeat_sync, src/cadrumo/application/user_profile, src/cadrumo/adapters/persistence/profile, dev/acceptance`.
- [ ] `S06` - pull previously filed declarations, expedientes and justificantes through CLI and TUI filed history, reconcile one modelo period against the local calculation, and prove a recapture creates no duplicates or drift; `aeat app live filed, aeat app live expedientes, aeat app live justificante, aeat app modelo reconcile pull`.
- [ ] `S07` - pull the IVA compensation wallet, prove its reconciliation decision against local 303 recurrence is surfaced, absence is never coerced to zero, and the representation screen is refused; `aeat app live iva-wallet`.
- [ ] `S08` - pull AEAT notifications and prove unread notifications remain unread at AEAT, documents are fetched only for already-read rows, and the TUI list matches the CLI; `aeat app live notifications`.
- [ ] `S09` - run the authenticated GROI check and record whether the write-token guard refuses its own surface; `aeat app live verify tgvi, src/cadrumo/domain/calculations/registry/remote_state_guard.py`.
- [ ] `S10` - verify Google Sheets push, pull and calculate parity, Drive evidence import and encrypted archive push with the operator completing OAuth consent in their own terminal; `aeat config google, aeat app modelo spreadsheet, aeat app ledger evidence pull, aeat config profile archive push`.
- [ ] `S11` - log out, confirm no session, diagnostic dump or plaintext residue remains, and record per-session evidence and residual findings in the feature audit; `aeat config auth logout, .vault/audit`.

## Parallelization

S01, S02 and S03 need no AEAT login and may run while the write-guard Step lands. S04 onward is strictly sequential and single-browser: one live process at a time, because sessions are per profile and the login lock serialises acquisition. S05 to S09 run inside one authenticated window opened by S04; if the 18 minute idle lifetime lapses, re-run S04 before continuing. S10 needs no AEAT session and may run in any window after S01. S11 is last.

## Verification

- Every live command is run through `uv run --env-file env/.env` with its exit status recorded; a timeout, refusal or AEAT-side blocker keeps its Step open and is recorded as a blocker, never as a pass.
- The browser process during S03 and S04 is the bundled Playwright chromium build, never an installed Chrome or Edge.
- CLI and TUI parity: for every surface the TUI reaches, the typed outcome set shown by the TUI equals the CLI outcome set for the same session.
- Reconciliation outcomes are surfaced with their typed codes; missing data is never shown as zero.
- No AEAT write: the no-write static scans and live-write refusal tests pass in S01, the browser-context guard from the write-guard plan is in place before S04, and unread notifications remain unread after S08.
- Code-sanity gates (ruff check and format, ty, pyrefly, basedpyright strict, import gate) are clean for any code written to support these sessions.
- The feature audit lists each Step's outcome, blockers and residual findings, with no taxpayer data.
