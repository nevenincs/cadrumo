---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S430'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S430`

## Description

- Tracks active-profile Google OAuth login/session persistence after folder and desktop-client registration.
- Required before repo-native `aeat config google sync probe --read-only` and enabled live Drive provider tests can pass.

## Outcome

Closed.

Evidence:

- `aeat config google folder get` reports a configured parent folder id for the pre-repair Drive setup.
- `aeat config google status` reports `client_registered=True` and `session_present=False`.
- `aeat config google sync probe --read-only` fails with the typed Google auth boundary because no OAuth token is persisted for the active profile.
- Enabled live Drive pytest fails provider construction at the same missing-token boundary instead of skipping.
- Continuation rerun on 2026-06-02 confirmed `aeat config google status` still reports `client_registered=True` and `session_present=False`.
- `aeat config google login --refresh-only` refused with a typed JSON error because no metadata/session exists to refresh.
- A bounded `aeat config google login` consent-flow attempt timed out after approximately 75 seconds, consistent with waiting for browser-based Google OAuth consent; a follow-up status check still reported `session_present=False`.
- Continuation rerun after operator authorization confirmed the expected live read-only active profile.
- `aeat config google register --help`, `aeat config google login --help`, `aeat config google folder --help`, and `aeat config google sync --help` confirm the repo-native setup path remains register/login/folder/sync, with calc-sheets export/verify/pull under `config google sync calc`.
- Current `aeat config google folder get` reports `configured=True` and the pre-repair root folder id.
- Current `aeat config google status` reports `client_registered=True`, the previously registered deleted client, and `session_present=False`.
- `aeat config google login` was retried as the repo-native loopback consent flow and timed out after 125 seconds without persisting a session; follow-up status still reported `session_present=False`.
- Local `gcloud` auth and ADC are present, but the current AEAT Drive provider does not consume ADC for `config google sync`; `src/aeat/adapters/outbound/storage/_factory.py` builds Google credentials only from the per-profile `google_oauth_client` plus `google_oauth_token` secure records.
- `aeat config google sync probe --read-only` refused at the typed Google auth boundary with `no Google OAuth token persisted for profile '<profile-id>'; run `aeat config google login` first`.
- A bounded background retry of `aeat config google login` was launched, but no session was persisted and no CLI output was emitted before cleanup.
- Multiple stale `aeat config google login` processes were found from earlier attempts; only exact `config google login` processes were stopped to clear loopback listeners before continuing.
- Final continuation rerun confirmed the command surface still only supports loopback browser login plus `--refresh-only`; no device-code or connector-token import path exists.
- `aeat config google login` was attempted with the active profile and timed out after approximately 180 seconds without persisting a token.
- Follow-up `aeat config google status` still reported `client_registered=True` and `session_present=False`.
- The leftover `config google login` process family from that timed-out attempt was stopped by exact PID; unrelated concurrent pytest, docs, and live-app processes were left untouched.
- The operator created a replacement Cloud Console Desktop client named `AEAT CLI` / `aeat-cli-client`; the downloaded Desktop-client JSON validates as an installed-client payload with `http://localhost` redirect.
- `aeat config google register --client-json <downloaded-desktop-client-json>` persisted the new Desktop client for the replacement Google Cloud project.
- `aeat config google login` completed the loopback consent flow for the operator's Google account; follow-up `aeat config google status` reported `session_present=True`, the new client id, and `reauth_required=False`.
- The first post-login `aeat config google sync probe --read-only` exposed a CLI payload/schema bug: provider reports may set `root_folder_present=None`, while `GoogleSyncProbeResult` previously required a strict boolean. `src/aeat/entrypoints/cli/_config/_google_payloads.py` now matches the provider contract and `src/aeat/entrypoints/cli/_config/test_google_sync_push.py` covers that boundary.
- The next post-fix probe reached Google but reported Drive API disabled for the replacement Google Cloud project; `gcloud services enable drive.googleapis.com sheets.googleapis.com --project=<replacement-google-cloud-project>` completed successfully and subsequent service listing confirmed both APIs enabled.
- With Drive enabled, the old persisted root folder was not visible to the new `drive.file` OAuth app context. A new app-owned root folder was created through the authenticated AEAT credentials and bound with `aeat config google folder set <app-owned-root-folder-id>`.
- Final `aeat config google sync probe --read-only` passed with `reachable=True`, `writable=False`, `root_folder_present=True`, and the app-owned root folder id.
- Focused validation passed: `ruff check src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py`; `pytest src/aeat/entrypoints/cli/_config/test_google_sync_push.py -q`; `AEAT_LIVE_TESTS_ENABLED=1 AEAT_LIVE_TESTS_GOOGLE=1 AEAT_STORAGE_PROVIDER_KIND=google_drive AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID=<app-owned-root-folder-id> pytest -m live_read src/aeat/adapters/outbound/storage/test_google_drive_live.py -q`.

Drive mutation note: the completed remediation created one new app-owned root folder in the operator's Drive and the live gate created then deleted `_probe` sentinel and manifest objects under that root folder. The old inaccessible folder id was not modified.
