---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P11.S36'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-live-auth-split-invariants-audit]]'
---

# W03.P11.S36 - Audit live and auth split invariants before implementation

Scope: record the live/auth split invariants before touching Playwright, encrypted session, active-profile identity, diagnostics, or live-read orchestration code.

## Description

- Audited current live/auth surfaces across application auth, application live, AEAT auth adapters, browser session construction, CLI live preflight, and remote-state guard policy.
- Recorded the invariants the next decomposition ADR must preserve.
- Left implementation out of scope because concurrent edits are present in the live/auth files.

## Outcome

- Added the dedicated live/auth split invariant audit.
- Identified S37 ADR boundaries:
  - application auth owns session acquisition and active-profile identity checks;
  - browser session owns Playwright context construction and certificate/storage-state injection;
  - provider adapters own provider-specific metadata, diagnostics capture, and verification mechanics;
  - application live owns live-read orchestration and persistence handoff;
  - CLI owns rendering only.
- Captured required regression evidence for the implementation slice.

## Verification

- Codebase discovery:
  - `fd . src/aeat/adapters/outbound/aeat src/aeat/entrypoints/cli -t f -e py`
  - `rg -n "storage_state|client_certificates|BrowserSession|Authenticator|certificate|thumbprint|active profile|profile|AEAT_LIVE|live gate|except Exception|exc_info|subprocess|env=|storageState|set_active_profile" src/aeat/adapters/outbound/aeat src/aeat/entrypoints/cli -g "*.py"`
  - targeted reads of `src/aeat/application/auth/_sessions.py`, `src/aeat/application/auth/_operator.py`, `src/aeat/adapters/outbound/aeat/auth/_session_store.py`, `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`, `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`, `src/aeat/adapters/outbound/aeat/browser/session.py`, `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py`, `src/aeat/application/live/__init__.py`, and `src/aeat/entrypoints/cli/_app_live.py`.
- Vault check:
  - `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- This was an audit-only step. No Ruff or pytest target was run because no production or test code was changed.
- The shared worktree is dirty and the branch had one existing local commit ahead of origin at the start of this slice. Live/auth implementation files were treated as read-only for this commit.
