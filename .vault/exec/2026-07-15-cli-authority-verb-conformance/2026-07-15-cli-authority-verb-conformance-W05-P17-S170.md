---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:4d1a3dcf3277bb4b372ead53ef84134f106e52d94fb50154d345422f9ac6096a'
step_id: 'S170'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Regenerate authentication sequence goldens for login, logout, reset, and certificate secrets

## Scope

- `docs/_sequences/how-to/authenticate-with-aeat/`

## Description

- Enumerated the 22 sequence contracts under `docs/_sequences/contracts/how-to/authenticate-with-aeat/`.
- Confirmed that eight of the 22 are `@static`: certificate-register, certificate-reregister, certificate-select, configure-renewed, configure, login-fresh, and login (all `credential-store` — need the OS credential store unavailable in the sandbox), plus secret-set (`interactive-tty` — refuses without a live terminal).
- Ran `python -m dev.docs.sequences refresh --page how-to/authenticate-with-aeat` to regenerate the 15 executed goldens.
- Verified the refreshed goldens pass the sequence contract check.

## Outcome

Verdict: SATISFIED.

Refresh command: `uv run --no-sync python -m dev.docs.sequences refresh --page how-to/authenticate-with-aeat`.
Output: `15 golden(s) rewritten`. All 15 executable sequences refreshed: profile, providers, readiness, check-validity, confirm-expiry, certificate-list, certificate-remove, certificate-check, logout-provider, reset-provider, reset-all, apoderado-scopes, apoderado-configure, apoderado-status, apoderado-clear. The eight `@static` contracts produce no golden; their `@blocked` annotations document the exact blocker for each.
Exit code 0. HEAD at run time: `9c4b780e1aed5c41938e16eaed2eccdcbddd3cfd`.

Static inventory (eight sequences verified against their contract files):

- `authenticate-certificate-register`: `@blocked credential-store` — needs certificate custody in the OS credential store, absent from the sandbox.
- `authenticate-certificate-reregister`: `@blocked credential-store` — needs certificate custody in the OS credential store, absent from the sandbox.
- `authenticate-certificate-select`: `@blocked credential-store` — needs a certificate registered in the OS credential store; the sandbox has none.
- `authenticate-configure-renewed`: `@blocked credential-store` — `aeat config auth configure --provider certificate` needs certificate custody absent from the sandbox.
- `authenticate-configure`: `@blocked credential-store` — `aeat config auth configure --provider certificate` needs certificate custody absent from the sandbox.
- `authenticate-login-fresh`: `@blocked credential-store` — `aeat config auth login --fresh` needs certificate custody absent from the sandbox.
- `authenticate-login`: `@blocked credential-store` — `aeat config auth login` needs certificate custody absent from the sandbox.
- `authenticate-secret-set`: `@blocked interactive-tty` — `aeat config auth certificate secret set` refuses when no interactive terminal is available.

## Notes

Check command: `uv run --no-sync python -m dev.docs.sequences check --page how-to/authenticate-with-aeat`. Output: `cli-sequence goldens: clean`. Exit code 0. All 15 refreshed goldens pass the sequence contract gate.
