---
tags:
  - '#audit'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# `live-pull-verification-sweep` audit: W02.P03 live auth blocker

## Scope

This audit covers the first W02.P03 authentication substrate pass for
`W02.P03.S08` and `W02.P03.S09`. The plan requires an authenticated Cl@ve
Movil or certificate session acquisition with the operator present, encrypted
storage-state persistence proof, and a focused live auth pytest lane under
explicit opt-in. The plan verification section also states that an external
auth blocker keeps the relevant step open.

## Findings

### BLOCKER - Initial authenticated session acquisition attempts could not complete without operator approval

Initial environment inspection found no credential material in the current
shell:

- `AEAT_SECRET_PASSPHRASE` present: false.
- `AEAT_LIVE_TESTS_ENABLED` before the focused run: unset.
- `AEAT_CERTIFICATE_PATH` present: false.
- `AEAT_CERTIFICATE_PASSWORD` present: false.
- `AEAT_CERTIFICATE_PASSWORD_SECRET` present: false.
- `AEAT_PROFILE` present: false.

After operator clarification, the run used the main worktree `env/.env` only
for the Cl@ve Movil NIE and NIE support-number settings, without printing or
persisting those raw values in vault evidence. A disposable process-local
`AEAT_SECRET_PASSPHRASE` was generated for an isolated profile root under
`.tmp/live-pull-auth-cli-20260612-164737`; this passphrase is local storage
encryption material, not an AEAT credential.

The corrected CLI path then created an isolated active profile and configured
Cl@ve Movil:

- `uv run aeat --format json config profile create ... --quiet --accept-defaults`
  succeeded and made the profile active.
- `uv run aeat --format json config auth configure --provider clave_movil`
  succeeded with `identity_alignment=matches`, `profile_tax_id_present=true`,
  and `provider_identity_present=true`.
- `uv run aeat --format json config auth test --provider clave_movil` succeeded
  with `configured=true`, `available=true`, `authenticated=false`,
  `persisted_session_state=no_session`, and health summary "Ready; requires
  operator-mediated Cl@ve completion."
- `uv run aeat --format json config auth login --provider clave_movil --fresh
  --reset-lock` reached AEAT's non-QR Cl@ve Movil flow but exited 3 after the
  configured 120 second timeout. Diagnostic id: `20260612T145006Z`.

The auth-login diagnostic reported:

- `auth_route=clave_movil_non_qr_request`.
- `identity_alignment=matches`.
- `identity_kind=NIE`.
- `nie_soporte_configured=true`.
- `verification_code_present=true`.
- `failure_mode=auth_completion_timeout`.
- `operator_report_required=true`.

This narrows the live blocker: the profile/passphrase/identity setup now works
in an isolated root, but no authenticated AEAT browser session was acquired
because operator-mediated Cl@ve completion did not finish inside 120 seconds.

A follow-up headed-browser attempt used a fresh isolated root
`.tmp/live-pull-auth-user-20260612-200824`, again with Cl@ve values read from
the main worktree `env/.env` and redacted from evidence:

- Profile creation succeeded.
- `config auth configure --provider clave_movil` succeeded with
  `identity_alignment=matches`.
- `config auth test --provider clave_movil` succeeded before and after the
  login attempt with `configured=true`, `available=true`,
  `authenticated=false`, and `persisted_session_state=no_session`.
- `config auth login --provider clave_movil --fresh --reset-lock` exited 3
  before a new approval could be completed because AEAT refused to issue a new
  Cl@ve Movil petition while a previous one remained pending server-side.
  Diagnostic id: `20260612T180844Z`.

The follow-up diagnostic reported `failure_mode=pending_petition_blocked`,
`reason=aeat-refused-new-clave-movil-petition`, and the retry instruction:
open the Cl@ve app, reject every pending request, then rerun the auth test or
wait up to five minutes for AEAT to expire the pending petition.

### PASS - Operator-assisted Cl@ve retry acquired a live persisted session

A later operator-assisted retry used a fresh isolated root
`.tmp/live-pull-auth-user-20260612-203142`, a generated process-local
`AEAT_SECRET_PASSPHRASE`, `AEAT_BROWSER_HEADLESS=false`, and the main worktree
`env/.env` Cl@ve settings with raw identity values redacted from output and
vault evidence.

Results:

- `config profile create` succeeded for the isolated profile.
- `config auth configure --provider clave_movil` succeeded with
  `identity_alignment=matches`, `profile_tax_id_present=true`, and
  `provider_identity_present=true`.
- `config auth test --provider clave_movil` before login succeeded with
  `configured=true`, `available=true`, `authenticated=false`, and
  `persisted_session_state=no_session`.
- `config auth login --provider clave_movil --fresh --reset-lock` succeeded
  with `authenticated=true`, `fresh=true`, `reused_persisted_session=false`,
  `removed_sessions=0`, and `acquired_lock=true`.
- `config auth status --provider clave_movil` after login succeeded with
  `configured=true`, `authenticated=true`, and `available=true`.
- `config auth test --provider clave_movil` after login succeeded with
  `authenticated=true`, `persisted_session_present=true`,
  `persisted_session_expired=false`, and `persisted_session_state=live`.

This confirms the isolated profile/passphrase/Cl@ve path can acquire and
persist a live AEAT session with the operator present. Raw NIE, soporte, and
passphrase values were not written to this audit.

### BLOCKER - S09 rerun attempts did not reacquire a persisted session

Two subsequent attempts tried to immediately use a fresh authenticated session
for the focused S09 pytest lane:

- `.tmp/live-pull-auth-s09-20260612-205830`
- `.tmp/live-pull-auth-s09-20260612-210153`

Both attempts created a fresh isolated profile and configured Cl@ve Movil with
`identity_alignment=matches`. Both then ran
`config auth login --provider clave_movil --fresh --reset-lock` with
`AEAT_BROWSER_HEADLESS=false`.

Both login attempts exited 3 with `failure_mode=auth_completion_timeout`,
`auth_route=clave_movil_non_qr_request`, `identity_alignment=matches`,
`identity_kind=NIE`, `nie_soporte_configured=true`, and
`verification_code_present=true`. Diagnostic ids:

- `20260612T190048Z`
- `20260612T190411Z`

After each timeout, `config auth test --provider clave_movil` reported
`authenticated=false`, `persisted_session_present=false`, and
`persisted_session_state=no_session`.

The focused pytest probe then ran:

`uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_playwright_entrypoint_reaches_live_selector src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_provider_probes_persisted_session_with_central_playwright -m aeat_live -q -rs`

Result on both attempts: 1 passed, 1 skipped. The selector probe passed, and
the persisted-session probe skipped because no persisted encrypted Cl@ve Movil
session was available to probe.

This keeps `W02.P03.S09` open. The intended next retry must approve the Cl@ve
request inside the 120 second AEAT window, then run the same persisted-session
pytest probe before the isolated process exits.

### INFO - Later S08 evidence supersedes the initial acquisition blocker

After this audit was first written, a separate S08 exec record appeared at
`.vault/exec/2026-06-12-live-pull-verification-sweep/2026-06-12-live-pull-verification-sweep-W02-P03-S08-W02-P04-S10-S11-S12-S13-W03-P06-S27-live-auth-read-sweep.md`.
That record reports a fresh Cl@ve Movil login success with
`authenticated=true`, `fresh=true`, `identity_alignment=matches`, and a live
persisted session, followed by authenticated read probes for censo, filed
history, expedientes, notifications, justificante list, and overview calendar.

The plan currently shows `W02.P03.S08` checked. This audit now records both
the failed attempts and the successful operator-assisted retry. The still-open
authentication row is `W02.P03.S09`: the focused live auth pytest lane has not
been rerun to no-skip green acceptance.

The focused live auth lane was then run with explicit opt-in only for the
process:

`uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_authenticator_live.py src/aeat/adapters/outbound/aeat/auth/tests/test_certificate_live.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py -m aeat_live -q -rs`

Result: 1 passed, 5 skipped in 6.35 seconds.

The passing test was the non-credentialed Cl@ve Movil selector reachability
probe. The skipped tests were credential or persisted-session dependent:

- `test_aeat_authenticator_synchronous_surface_live`: AEAT certificate env vars
  are not fully configured.
- `test_aeat_authenticator_full_live_flow`: AEAT certificate env vars are not
  fully configured.
- `test_verify_handshake_live_against_aeat`: AEAT certificate env vars are not
  fully configured.
- `test_clave_movil_provider_probes_persisted_session_with_central_playwright`:
  no persisted encrypted Cl@ve Movil session is available to probe.
- `test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled`:
  `AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH` is not `1`.

Because the first focused lane still contains credential/session skips,
`W02.P03.S09` is not green acceptance. The plan's checked `W02.P03.S08` status
is now consistent with both the later S08 exec record and the successful
operator-assisted retry recorded in this audit.

### PASS - Local encrypted browser-session persistence remains intact

The storage substrate portion was verified with the existing real-behavior test:

`uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py -q`

Result: 1 passed in 0.70 seconds.

The test uses a real isolated active profile-bucket runtime and
`SecureObjectRepository`, saves a Playwright-shaped `storage_state`, loads it
back through `src/aeat/adapters/outbound/aeat/auth/_session_store.py`, verifies
the `SESSION` classification and schema version, verifies the object key is not
stored as the plaintext logical path, and verifies that no plaintext
`storage_state` file or sidecar is created.

### INFO - Predecessor blocker remains relevant

Same-day live censo/calendar evidence already recorded the broader live
dependency: profile-bound AEAT proof requires a profile passphrase and a
profile tax identity matching the identity used during AEAT authentication.
Earlier authenticated attempts either timed out during operator-mediated Cl@ve
completion or reached AEAT G313 without returning a readable censo for the
configured profile identity.

## Recommendations

- Keep `W02.P03.S09` unchecked until the focused live auth lane is rerun with
  explicit opt-in and the remaining skips or failures are eliminated or
  formally carried as open acceptance blockers.
- For the Cl@ve path, rerun the isolated profile/auth setup, keep the app open,
  and approve only when the phone request matches the AEAT verification code
  shown by the CLI.
- If AEAT reports `pending_petition_blocked`, clear pending requests in the
  Cl@ve app before rerunning; otherwise AEAT will not issue a fresh petition.
- Run the focused auth lane again with `AEAT_LIVE_TESTS_ENABLED=1` and no skip
  outcomes before treating W02.P03 auth proof as green acceptance.
- If Cl@ve Movil is used, ensure the active profile tax identity matches the
  operator-authenticated AEAT identity before using the session for censo,
  calendar, filed-history, justificante, or IVA proof.

## Codification candidates

None. The existing plan already codifies the rule that external live auth
blockers keep the relevant step open.

## Update 2026-06-12 - Fresh Cl@ve auth succeeded; downstream live blockers narrowed

The later authenticated run used a fresh isolated encrypted profile root and the
operator-completed Cl@ve Móvil flow. The profile was created with a tax identity
matching the Cl@ve identity, `config auth configure --provider clave_movil`
reported `identity_alignment=matches`, and `config auth login --provider
clave_movil --fresh --reset-lock` returned `authenticated=true`, `fresh=true`,
and `reused_persisted_session=false`.

The authentication substrate blocker for `W02.P03.S08` is resolved by this run
plus the encrypted session-store roundtrip test. Remaining blockers are now
downstream live-read blockers:

- `W02.P03.S09` remains open because the full focused live auth pytest lane was
  not rerun to no-skip green acceptance; only the selector probe was rerun and
  passed under `AEAT_LIVE_TESTS_ENABLED=1`.
- `W02.P04.S10` remains open because censo/Modelo 036 pull reached AEAT but
  refused with `AEAT sede G313 returned no readable censo for profile`; no censo
  snapshot exists for profile/censo comparison or calendar reconciliation.
- `W02.P04.S11` remains open because Modelo 303 filed-history read for 2026
  succeeded with zero rows, but the all-model filed-history read for 2026 timed
  out after 180 seconds while still in authenticated preflight. No filed row was
  available for justificante pull/enrollment proof.
- `W02.P04.S12` has a positive Modelo 303 expedientes probe for 2026 with a
  persisted snapshot and zero declarations, but broader expedientes coverage
  remains open.
- `W02.P04.S13` has a positive notifications pull with one persisted row, and
  `W03.P06.S27` has positive calendar projection of that row as a message event.
  Censo-derived obligation reconciliation remains blocked by the G313 censo
  result.

## Update 2026-06-12 - All-model filed-history timeout resolved as bounded partial success

The all-model filed-history blocker was narrowed. The implementation now bounds
each AEAT filed-register Modelo/year query with
`aeat_live_filed_register_walk_timeout_ms` and moves all-model listing into a
backend `list_filed_data_bulk` facade that uses one authenticated register
session. The CLI still exposes this through `app live filed list` and
`app live filed pull`; `app live filed pull-all` remains unregistered.

Authenticated rerun against the same isolated live Cl@ve profile completed:

- `app live filed list --from-year 2026 --to-year 2026` returned
  `row_count=0`, `failed_count=8`, and explicit local-boundary failures for
  unsupported/no-revision models.
- `app live filed pull --from-year 2026 --to-year 2026` returned
  `captured_count=0`, `failed_count=8`, no observations, no artefacts,
  `justificante_metadata_count=0`, and `filing_evidence_stamped_count=0`.

`W02.P04.S11` remains open, but no longer because all-model filed history hangs.
It remains open because the authenticated AEAT account state returned no filed
declaration row to use for positive single-pull, source-pull, justificante
download, and filing-evidence enrollment proof.

## Update 2026-06-12 - Calendar now refuses unverified censo enrolment

The live censo blocker remains open. A fresh authenticated `config profile censo
pull` against the same isolated Clave Movil profile reached AEAT G313 and again
returned no readable censo for the profile identity.

The calendar behavior is now hardened around that blocker:

- `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`
  returns the provisional live-profile calendar, including AEAT notification
  message events and per-obligation `justificante_required=true` /
  `justificante_verified=false` filing evidence.
- The calendar includes `censo.enrolment_unverified` for affected modelos
  `100`, `303`, `390`, and `721` because the active profile facts do not carry
  live censo provenance.
- Strict calendar mode refuses on that warning instead of silently treating
  profile-derived obligations as live-reconciled censo obligations.

`W02.P04.S10` remains open until AEAT returns readable Modelo 036/censo facts
that can be applied to the profile. `W03.P05.S19` and `W03.P06.S27` remain open
for positive censo-backed projection, but the negative/live-blocked calendar
state is now explicit and operator-visible.

## Update 2026-06-12 - Cl@ve pending petition blocked this live rerun

The next live rerun started from the same isolated live root and auth status
reported the Cl@ve provider configured, authenticated, available, and aligned
with the active profile identity. However, `config profile censo pull` again
entered the AEAT Cl@ve Movil non-QR request flow and timed out before operator
completion. AEAT then refused the filed-history live read because a prior
Cl@ve petition was still pending server-side.

Observed live outcomes:

- `config profile censo pull`: `failure_mode=auth_completion_timeout`,
  diagnostic `20260612T174432Z`, `verification_code_present=true`.
- `app live filed list --modelo 303 --from-year 2026 --to-year 2026`:
  `failure_mode=pending_petition_blocked`, diagnostic `20260612T174527Z`.
- `app live filed pull-all --help`: rejected with `No such command 'pull-all'.
  Did you mean 'pull'?`.
- `app overview calendar --from 2026-01-01 --to 2026-12-31
  --allow-incomplete`: local projection succeeded with seven Modelo entries,
  one AEAT notification event, no verified justificantes, and
  `censo.enrolment_unverified`.

The live rows remain open. The next operator action is to open the Cl@ve app,
reject every pending request, and rerun the live `pull` commands after AEAT
clears the pending-petition guard.

## Update 2026-06-12 - Pending petition cleared; filed pull proves empty account state

AEAT later cleared the pending Cl@ve petition. The same isolated live root then
reported Cl@ve configured, authenticated, available, and aligned to the active
profile.

Authenticated live results:

- `app live filed list --modelo 303 --from-year 2026 --to-year 2026` completed:
  `row_count=0`, `failed_count=0`.
- `app live filed pull --modelo 303 --year 2026 --limit 1` completed:
  `captured_count=0`, `justificante_metadata_count=0`,
  `filing_evidence_stamped_count=0`, no artefact refs, no observation paths.
- `config profile censo pull` reached AEAT G313 and refused with no readable
  censo for the profile identity.
- `app overview calendar --from 2026-01-01 --to 2026-12-31
  --allow-incomplete` continued to project seven Modelo rows, one AEAT
  notification message event, no AEAT filing evidence, no verified
  justificantes, and the `censo.enrolment_unverified` warning.

The prior pending-petition blocker is no longer the active blocker. The live
filed-history path itself is operational for the tested Modelo/year, but the
authenticated AEAT account state contains no filed Modelo 303 row for 2026 to
download, parse, enroll, or reconcile. Positive censo proof remains blocked by
G313 returning no readable censo.

## Update 2026-06-12 - Fresh live-auth retries reached AEAT but timed out

During the calendar justificante-warning hardening pass, live auth was retried
against the same isolated root before rerunning censo/filed pulls. The local
auth projection still reported Cl@ve configured, authenticated, available, and
identity-aligned, but the persisted browser session was missing after the fresh
attempt and AEAT required operator-mediated Cl@ve completion again.

Observed live outcomes:

- `config auth login --provider clave_movil --fresh` reached the AEAT non-QR
  Cl@ve route and timed out with `verification_code_present=true`, diagnostic
  `20260612T180957Z`.
- A concurrent censo/filed probe correctly tripped the single Cl@ve acquisition
  lock: `app live filed list --modelo 303 --from-year 2026 --to-year 2026`
  refused while `config profile censo pull` owned the live auth operation.
- Sequential `config auth login --provider clave_movil` reached the AEAT
  non-QR route and timed out with diagnostic `20260612T181507Z`.
- QR-mode `config auth login --provider clave_movil` with
  `AEAT_CLAVE_PREFER_NON_QR=false` reached the AEAT QR route and timed out with
  diagnostic `20260612T181925Z`.

No destructive recovery was run. The next live acceptance pass must start with
one completed Cl@ve login, then run live censo, filed list, filed pull, and
calendar projection sequentially. The positive censo/filed/justificante rows
remain open because AEAT auth completion did not finish in this pass.

## Update 2026-06-12 - Focused live auth pytest lane run under opt-in

The focused auth pytest lane for `W02.P03.S09` was run with
`AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH=1`, and
`AEAT_CLAVE_PREFER_NON_QR=false`.

Result: 6 selected live-auth tests produced 1 pass, 4 skips, and 1 failure.
The passing test proved the central Playwright browser reaches AEAT's live
Clave Movil selector. The skipped tests were not counted as acceptance: three
certificate tests skipped because certificate env vars are not configured, and
one Clave persisted-session probe skipped because the pytest-isolated root had
no persisted encrypted Clave session. The full Clave login reached AEAT QR mode,
displayed verification code `S2J`, and failed after 120 seconds waiting for
post-auth landing. The provider captured encrypted diagnostic
`20260612T182744Z` and confirmed cancellation of the pending Clave request.

Local auth substrate checks passed separately: the live-read access gate suite
reported 12 passed, and the encrypted session-store/resume suites reported 12
passed. Therefore the current blocker is live operator-mediated auth completion
and missing certificate credentials, not the local auth gate or encrypted
session-store implementation.

## Update 2026-06-12 - Fresh censo CLI pull root reached Cl@ve but timed out

A new isolated live root was created for censo CLI verification after the censo
surface was hardened to emit the shared live-auth preflight.

Local setup succeeded:

- `config profile create` created a fresh active profile whose tax id matched
  the configured Cl@ve identity.
- `config auth configure --provider clave_movil` reported provider configured,
  profile tax id present, Cl@ve identity present, and identity alignment
  `matches`.
- `config auth status --provider clave_movil` reported provider configured and
  available, with no persisted authenticated session.

Authenticated live attempts:

- QR-mode `config profile censo pull` reached AEAT Cl@ve, emitted
  `auth_preflight=redacted`, then timed out before completion with diagnostic
  `20260612T184841Z`.
- non-QR `config profile censo pull` reached AEAT Cl@ve, emitted
  `auth_preflight=redacted`, then timed out before completion with diagnostic
  `20260612T185117Z`.

Both attempts carried `auth_identity_alignment=matches`,
`auth_probe_result=ok`, and `verification_code_present=true`. No live censo
snapshot was captured, so `show`, `compare`, `apply`, and live-backed calendar
projection could not be completed in this pass. The open blocker remains
operator-mediated Cl@ve completion, not local profile creation, auth
configuration, identity alignment, or censo CLI command routing.

## Update 2026-06-12 - S09 Cl@ve pytest lane passed after same-root persistence proof

The earlier S09 persisted-session skip was traced to test isolation rather than
to the Cl@ve provider or encrypted session store. The live auth test package
enters `isolated_runtime_profile(..., bucket_id="auth-session")` for each
pytest case, so a session created by a separate CLI process in `.tmp/...` is not
visible to `test_clave_movil_provider_probes_persisted_session_with_central_playwright`.

The live full-login test was therefore tightened to prove the real persistence
contract inside the same pytest-isolated runtime that performs the
operator-mediated login. After successful `authenticate()` and `verify()`, it
asserts that `clave-movil-storage` exists in the encrypted session store, that
no plaintext storage-state or metadata file exists on disk, closes the first
provider, creates a fresh provider, and runs `probe_persisted_session()` through
the central Playwright backend.

Fresh opt-in checks then passed:

- `AEAT_LIVE_TESTS_ENABLED=1 AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH=1
  AEAT_CLAVE_PREFER_NON_QR=true AEAT_BROWSER_HEADLESS=false uv run pytest
  src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled
  -m aeat_live -q -rs --tb=short`: 1 passed in 28.65 seconds.
- `AEAT_LIVE_TESTS_ENABLED=1 AEAT_BROWSER_HEADLESS=true uv run pytest
  src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py::test_clave_movil_playwright_entrypoint_reaches_live_selector
  -m aeat_live -q -rs --tb=short`: 1 passed in 1.85 seconds.
- `uv run ruff check
  src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py`:
  passed.

This closes the Cl@ve path for `W02.P03.S09`: the focused opt-in lane now has
non-interactive selector reachability plus operator-authenticated session
creation, encrypted persistence, fresh-provider resume, and live verification.
Certificate live tests remain outside this acceptance proof because certificate
credentials are not configured in the environment.

## Update 2026-06-12 - S10 censo rerun blocked by pending Cl@ve petition

A fresh isolated live root was created for `W02.P04.S10` under
`.tmp/live-censo-s10-20260612-233113`. The setup used file-backed secret
storage, a process-local passphrase, a profile tax id matching the configured
Cl@ve identity, visible browser mode, and the main worktree Cl@ve identity
settings with raw values redacted from command output.

Local setup succeeded:

- `config profile create` created and activated the fresh profile.
- `config auth configure --provider clave_movil` returned `complete=true`,
  `profile_tax_id_present=true`, `provider_identity_present=true`, and
  `identity_alignment=matches`.
- `config auth status --provider clave_movil` returned `configured=true`,
  `available=true`, and `authenticated=false`, with health summary indicating
  operator-mediated Cl@ve completion was required.

The authenticated rerun did not get to censo data retrieval:

- `config auth login --provider clave_movil --fresh --reset-lock` exited 3
  with `failure_mode=pending_petition_blocked`, diagnostic
  `20260612T213139Z`.
- `config profile censo pull` emitted the redacted live-auth preflight with
  `auth_identity_alignment=matches`, `auth_mode=non_qr`,
  `auth_nie_soporte=present`, and `auth_probe_result=ok`, then exited 3 with
  `failure_mode=pending_petition_blocked`, diagnostic `20260612T213158Z`.
- `config profile censo show`, `compare`, and `apply` each refused because no
  censo snapshot had been captured for the isolated profile.

No S10 completion is claimed. The active live blocker for this attempt is AEAT's
pending Cl@ve petition guard; the operator must reject pending Cl@ve requests
in the app or wait for AEAT to time them out before the censo pull can be
retried.

## Update 2026-06-12 - Calendar projection live sweep blocked by noninteractive secret unlock

After the calendar evidence projection hardening landed, local CLI/backend
checks were green and the next acceptance target was the user-requested live
read sweep: auth status/login, Modelo 036 censo pull/compare, filed history
pull, expedientes pull, notifications pull, and overview calendar projection
using `pull` commands only.

The Codex command runner cannot read passphrase prompts from stdin. A direct
`config auth status` attempt failed before any AEAT contact with:
`AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive`. A visible
PowerShell helper was launched to let the operator enter the passphrase and run
the read-only sweep, but it did not produce an observable log in this shared
runner and was stopped rather than left waiting for secrets.

No live positive censo, filed-history, justificante, notifications,
expedientes, or calendar aggregation result is claimed in this update. The
remaining operational requirement is to provide `AEAT_SECRET_PASSPHRASE` to
the Codex Settings environment or run the documented commands in an
interactive terminal where the CLI can prompt for the secure-storage
passphrase and AEAT authentication.

## Update 2026-06-13 - Fresh isolated live sweep timed out during Cl@ve approval

A new isolated live root was created under `Y:\tmp\aeat-live-sweep-20260613-074016`
to avoid relying on the default locked profile. The run used file-backed secret
storage, a generated process-local passphrase, visible-browser Cl@ve mode, and
the configured Cl@ve identity from the environment without printing raw identity,
support-number, passphrase, token, or storage-state values.

Local setup succeeded:

- `config profile create ... --quiet --accept-defaults` exited 0 and created the
  active live-sweep profile.
- `config auth configure --provider clave_movil` exited 0 with
  `complete=true` and `identity_alignment=matches`.

The authenticated live pass did not acquire a session:

- `config auth login --provider clave_movil --fresh --reset-lock` exited 3 after
  approximately 130 seconds with
  `AUTH_AUTH_CLAVE_MOVIL_CLAVE_MOVIL_APPROVAL_TIMEOUT`.
- `config auth status --provider clave_movil` exited 0 and reported
  `configured=true`, `authenticated=false`.
- `config profile censo pull`, `app live filed list --from-year 2026
  --to-year 2026`, and `app live notifications pull` each reached the redacted
  auth preflight and then exited 3 because no authenticated session was available.
- `config profile censo compare` refused because no censo snapshot existed.
- `app live filed pull --from-year 2026 --to-year 2026 --limit 25` refused at
  the local/auth boundary after the failed session attempt.
- `app overview calendar --from 2026-01-01 --to 2026-12-31
  --allow-incomplete` exited 0 as a local projection, but it is not positive
  live-backed censo/filed/justificante evidence.

No new positive live censo, filed-history, justificante, notifications, or
calendar aggregation result is claimed by this update. The current blocker is
operator-mediated Cl@ve approval not completing inside the AEAT request window;
the local profile creation, generated passphrase, provider configuration, and
identity-alignment path are operational.

## Update 2026-06-13 - Isolated profile/password flow works; Cl@ve still times out

The continuation created a new isolated encrypted profile store under
`var/live-auth-sweep-20260613` instead of trying to unlock the shared default
runtime. This directly checks the operator concern that a user must be able to
create a profile and password for live CLI operation.

Local setup succeeded:

- `config profile create codex-live-20260613 ... --quiet --accept-defaults`
  exited 0 and activated the isolated profile.
- `config auth configure --provider clave_movil` exited 0 with
  `profile_tax_id=present`, `clave_identity=present`, and
  `identity_alignment=matches`.
- `config profile status` exited 0 for the isolated profile with the tax id
  redacted to a fingerprint.

The authenticated live session still did not complete:

- Headless non-QR `config auth login --provider clave_movil --fresh
  --reset-lock` timed out at diagnostic `20260613T061642Z`.
- Visible non-QR login timed out at diagnostic `20260613T061921Z`.
- Visible QR login timed out at diagnostic `20260613T062143Z`.
- `config auth status --provider clave_movil` then reported
  `configured=True`, `authenticated=False`, and operator-mediated Cl@ve
  completion required.
- `config auth diagnostics report 20260613T062143Z --phone-state
  operator_did_not_check` recorded the latest attempt's phone-state
  uncertainty.

The scoped non-live regression gates were rerun and passed after this live
attempt:

- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py
  src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q`
  passed 36 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py
  src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q` selected
  40 application tests under default marker filtering and passed them.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  passed 19 CLI calendar tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py
  src/aeat/entrypoints/cli/tests/test_registry_cli.py -q` passed 81 command
  surface tests and preserves the `pull`-only/no-`pull-all` guard.

## Update 2026-06-13 - Visible live-auth runner did not advance past passphrase prompt

After the notification/calendar taxpayer-scope hardening, a visible PowerShell
live-auth runner was launched from `var/aeat/live-auth-run/run-live-auth.ps1`
with read-only live flags:

- `AEAT_BROWSER_HEADLESS=false`
- `AEAT_OUTPUT_LANGUAGE=en`
- `AEAT_LIVE_TESTS_ENABLED=1`
- `AEAT_CLAVE_PREFER_NON_QR=true`

Before launching the runner, the prior short passphrase candidate `horatio` was
tested against the isolated `var/live-auth-sweep-20260613` root and refused by
the CLI with `REFUSED_STORAGE_PASSPHRASE_TOO_SHORT`; it is seven characters and
does not satisfy the configured minimum. The current shell also had no
`AEAT_CLAVE_MOVIL_DNI_NIE`, `AEAT_CLAVE_MOVIL_DNI_FECHA`, or
`AEAT_CLAVE_MOVIL_NIE_SOPORTE` environment variables, so a brand-new
non-interactive live profile could not be created from flags in this process.

The visible runner process stayed alive but did not create its redacted log
after repeated checks. That means it did not reach `config auth status`,
`config auth login`, AEAT Cl@ve, censo pull, filed pull, notifications pull, or
calendar projection; it was still before command execution, consistent with
waiting at the secure-storage passphrase prompt. The idle runner process was
stopped to avoid leaving an orphaned passphrase prompt.

No positive live censo, Modelo 036, filed-history, justificante, notification,
or live-backed calendar evidence is claimed from this attempt. The live blocker
for this update is local credential entry/identity availability, not an AEAT
transport result.

No positive live Modelo 036/censo, filed-history, justificante, notification,
or live-backed calendar aggregation evidence is claimed by this update.

## Update 2026-06-13 - Fresh interactive profile handoff launched, awaiting operator input

After the CSV-register justificante-bound hardening, a new fresh-profile live
handoff was launched instead of attempting to unlock the shared default store.
The visible PowerShell window uses isolated storage at
`var/live-auth-20260613-operator` with:

- `AEAT_LOCAL_STORAGE_ROOT=var/live-auth-20260613-operator`
- `AEAT_SECRET_STORE_BACKEND=file`
- `uv run aeat config profile create live-auth-20260613`

The first launch attempt had malformed PowerShell environment assignment due to
interpolation in the supervisor shell. That supervisor-owned process tree was
stopped, then the command was relaunched with escaped `$env:` assignments.

The corrected interactive process is alive and has created only
`var/live-auth-20260613-operator/logs/aeat.log`. No profile bucket, encrypted
store, or active-profile pointer exists yet after repeated polls. This means
the profile wizard is still awaiting operator input in the visible window or
the window is not focused.

No `config auth configure`, `config auth login`, censo Modelo 036 pull, filed
history pull, justificante pull, notifications pull, or live-backed calendar
aggregation has run in this fresh store yet. No positive live evidence is
claimed from this attempt. The live blocker remains operator completion of the
fresh profile/password/authentication handoff.

## Update 2026-06-13 - Isolated secret-store runner reached Cl@ve but timed out

The live runner was hardened and relaunched with a fully isolated storage
substrate:

- `AEAT_LOCAL_STORAGE_ROOT=var/live-auth-20260613-operator-isolated`
- `AEAT_SECRET_STORE_DIR=var/live-auth-20260613-operator-isolated/secrets`
- `AEAT_BLOB_STORE_DIR=var/live-auth-20260613-operator-isolated/blobs`
- `AEAT_SECRET_STORE_BACKEND=file`
- generated process-local passphrase, removed from the supervisor shell after
  launch

The runner command list was also corrected to use `pull` acquisition verbs only.
The authenticated sequence no longer contains a live `pull-all` command. It
targets censo pull/compare, filed list/pull, expedientes pull, notifications
pull, justificante pull/list, and a 2025-2027 overview calendar projection.

Local setup succeeded:

- `config profile create live-auth-20260613-isolated ...` exited 0 and
  activated the isolated profile.
- `config auth configure --provider clave_movil` exited 0, with profile tax id
  present, Cl@ve identity present, and identity alignment reported as matching.
- `config auth status --provider clave_movil` exited 0 before login with
  `configured=True`, `authenticated=False`, and active profile ready.
- The isolated root contains an active-profile pointer, a bucket database, an
  encrypted `master.key` under the isolated `secrets` directory, and a token
  directory.

The authenticated live session did not complete:

- `config auth login --provider clave_movil --fresh --reset-lock` exited 3 with
  `auth_completion_timeout`; diagnostic id `20260613T110618Z`.
- `config auth status --provider clave_movil` then reported
  `configured=True`, `authenticated=False`.
- `config profile censo pull` reached auth preflight and then exited 3 with
  `auth_completion_timeout`; diagnostic id `20260613T110838Z`.
- `config profile censo compare` refused because no censo snapshot existed.
- `app live filed list --from-year 2025 --to-year 2026` entered another auth
  preflight; the runner was stopped there to avoid repeating the same timeout
  across filed, expedientes, notifications, justificante, and calendar steps.

No positive live Modelo 036/censo, filed-history, justificante, notification,
expediente, or live-backed calendar evidence is claimed by this update. The
current blocker is operator-mediated Cl@ve completion: the browser reached the
non-QR Cl@ve confirmation flow and displayed verification codes, but AEAT did
not reach the post-auth landing page before the configured 120000 ms timeout.
