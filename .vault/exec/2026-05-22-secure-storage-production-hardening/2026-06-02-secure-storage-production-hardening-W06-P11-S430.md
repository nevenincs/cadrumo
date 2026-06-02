---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
step_id: 'S430'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W05-P10-S43-review]]'
---

# `secure-storage-production-hardening` `W06.P11.S430`

## Description

- Tracks active-profile Google OAuth login/session persistence after folder and desktop-client registration.
- Required before repo-native `aeat config google sync probe --read-only` and enabled live Drive provider tests can pass.

## Outcome

Open.

Evidence:

- `aeat config google folder get` reports the parent folder id `1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`.
- `aeat config google status` reports `client_registered=True` and `session_present=False`.
- `aeat config google sync probe --read-only` fails with the typed Google auth boundary because no OAuth token is persisted for the active profile.
- Enabled live Drive pytest fails provider construction at the same missing-token boundary instead of skipping.
- Continuation rerun on 2026-06-02 confirmed `aeat config google status` still reports `client_registered=True` and `session_present=False`.
- `aeat config google login --refresh-only` refused with a typed JSON error because no metadata/session exists to refresh.
- A bounded `aeat config google login` consent-flow attempt timed out after approximately 75 seconds, consistent with waiting for browser-based Google OAuth consent; a follow-up status check still reported `session_present=False`.
- Continuation rerun after operator authorization confirmed the active profile is `live-iva-readonly-20260602`.
- `aeat config google register --help`, `aeat config google login --help`, `aeat config google folder --help`, and `aeat config google sync --help` confirm the repo-native setup path remains register/login/folder/sync, with calc-sheets export/verify/pull under `config google sync calc`.
- Current `aeat config google folder get` reports `configured=True` and root folder id `1ia6jGjO2Dasm8Fn5cYcgrDSSwW5X8MHQ`.
- Current `aeat config google status` reports `client_registered=True`, client id ending `...l62otqf.apps.googleusercontent.com`, and `session_present=False`.
- `aeat config google login` was retried as the repo-native loopback consent flow and timed out after 125 seconds without persisting a session; follow-up status still reported `session_present=False`.
- Local `gcloud` auth and ADC are present, but the current AEAT Drive provider does not consume ADC for `config google sync`; `src/aeat/adapters/outbound/storage/_factory.py` builds Google credentials only from the per-profile `google_oauth_client` plus `google_oauth_token` secure records.
- `aeat config google sync probe --read-only` refused at the typed Google auth boundary with `no Google OAuth token persisted for profile '<profile-id>'; run `aeat config google login` first`.
- A bounded background retry of `aeat config google login` was launched, but no session was persisted and no CLI output was emitted before cleanup.
- Multiple stale `aeat config google login` processes were found from earlier attempts; only exact `config google login` processes were stopped to clear loopback listeners before continuing.
- Final continuation rerun confirmed the command surface still only supports loopback browser login plus `--refresh-only`; no device-code or connector-token import path exists.
- `aeat config google login` was attempted with the active profile and timed out after approximately 180 seconds without persisting a token.
- Follow-up `aeat config google status` still reported `client_registered=True` and `session_present=False`.
- The leftover `config google login` process family from that timed-out attempt was stopped by exact PID; unrelated concurrent pytest, docs, and live-app processes were left untouched.

No Drive files were created, moved, or deleted while investigating this blocker.
