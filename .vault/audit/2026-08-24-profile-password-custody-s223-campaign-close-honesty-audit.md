---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3bc56d986cfec635d586d50419da38499643cd7cb325a13d1c289e207ed51e90'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-18-profile-password-custody-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-fresh-context-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-s206-recovery-parity-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s209-posix-kdf-descriptor-attestation-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s220-exec-evidence-audit]]"
  - "[[2026-08-24-profile-password-custody-s219-docs-audit]]"
  - "[[2026-08-24-profile-password-custody-s222-platform-gate-audit]]"
---
# `profile-password-custody` audit: `fresh-context campaign-close honesty review`

## Scope

Fresh-context campaign-close review of the accepted mandatory verified recovery-at-creation contract and current implementation. The review independently traced the governing custody and machine-secret decisions through the application registration boundary, scripted CLI, terminal manager, full-screen TUI, capsule storage, restore-only recovery paths, password-login independence, direct caller inventory, operator documentation, execution-record ledger, S221 recovery matrix, S222 native Windows and WSL platform evidence, and the historical 2026-08-18 close pointer. It also re-ran focused real application, TUI, scripted CLI, documentation-sequence, and feature-scoped Vaultspec gates at current HEAD while preserving unrelated peer work.

## Findings

### mandatory-recovery-contract | pass | Decision and current code agree at every creation boundary

The accepted roll-up requires exact recovery possession before publication, no password-only creation outcome, no later enrollment writer, restore-only recovery authority, and password-login independence. `register_profile_with_credentials` requires a recovery handoff in its signature, mints and verifies the exact phrase before entering capsule publication, wipes the recovery key on every exit, and reports enrolled recovery only after success. `ProfileCapsuleLifecycle.create` independently refuses absent recovery material. The scripted CLI supplies bounded stdin or descriptor recovery channels; the terminal manager and full-screen TUI keep exact confirmation inside their pre-publication handoffs. Every direct caller found under `src` supplies the required callback, including the shared provisioning and harness doors. Recovery minting has no production caller outside registration, restore republishes the existing password envelope rather than enrolling or rotating recovery, and normal password login succeeds after the committed recovery wrapper is removed or damaged.

Focused current-HEAD evidence passed: 13 application, password-login-independence, and TUI tests; 36 scripted profile-creation tests; and both generated sequence checks for `how-to/profile-setup` and `how-to/protect-data-access`. The profile-setup sequence debt recorded during S219 is therefore resolved in the current tree. The guide truthfully states that the CLI does not currently export the separate portable recovery artifact; it does not misrepresent the mnemonic alone as a complete off-host recovery path.

### evidence-ledger-and-platform-close | pass | Reconciled records and refreshed native matrices support the checked work

The S220 adjudication leaves no checked Step without required execution-record body evidence, and the plan-to-record mapping is bijective before this final record is added. S221 records green application, scripted CLI, terminal, TUI, Windows inherited-handle, and WSL POSIX descriptor coverage. S222 records current-collection native Windows and isolated-WSL matrices of 19 KDF tests and 70 machine-secret subprocess tests per platform, without counting platform skips as proof. Source review confirms same-scope and cross-scope channel conflicts and inapplicable root sources refuse during selection or preflight before profile-session activation. The earlier 2026-08-18 close is explicitly marked historical and directs readers to Wave W06 and the successor honesty review.

No CRITICAL, HIGH, or MEDIUM inconsistency remains between the accepted decisions, implementation, documented current capability, execution evidence, or platform proof.

### refusal-snapshot-excludes-session-receipts | low | Refusal tests omit two side-effect classes from their durable witness

The S222 LOW note is real but does not warrant escalation on current evidence. All three snapshot helpers in `test_machine_secret_channels_subprocess.py` exclude filenames containing `session` or `receipt`; consequently their equality assertions could miss a future refusal-path regression that creates, deletes, or replaces one of those artifacts. A focused independent integration run covering same-scope conflicts, cross-scope collisions, descriptor refusals, and root-source inapplicability passed 19 tests. More importantly, current production ordering raises same-scope conflicts in secure-input selection, cross-scope conflicts in profile-authentication preflight, and root-source inapplicability before the session-activation branch. No reachable mutation or current custody defect was found. The consequence is a bounded test-witness weakness, so LOW is honest; an observed persisted acceleration session or receipt on refusal would instead be HIGH.

## Recommendations

Approve S223 and campaign closure: no CRITICAL, HIGH, or MEDIUM blocker remains, the governing decisions and current code agree, the checked execution ledger is supported, and current Windows, POSIX/WSL, application, CLI, TUI, documentation, and Vaultspec evidence is green.

Retain the refusal-snapshot item as the formally deferred LOW hardening recommendation already grounded in the S222 platform-gate audit. A follow-on test-only change should include session and receipt artifacts in the exact conflict and inapplicability witnesses, or assert their absence separately, without changing the production ordering or weakening the unread-channel assertions. This deferral excludes only a broader regression witness; it does not exclude the standing goal's requirement that present refusal ordering precede session activation, which source inspection and focused real subprocess tests establish at current HEAD.
