---
tags:
  - '#audit'
  - '#provider-sign-in'
date: '2026-10-17'
modified: '2026-10-18'
body_schema: 'body-v2'
body_hash: 'sha256:c5e27b34a8cd3ca27cebcae1758812e8fdedb7e2aacb0b2974d6c1bd276eef7f'
related:
  - "[[2026-10-17-provider-sign-in-plan]]"
---
# `provider-sign-in` audit: Desktop CLI sign-in integration

## Scope

Uncommitted work under the approved provider-sign-in plan in the Cadrumo feature/tui checkout, with the sibling agent main checkout supplying the hidden helper and GUI capability catalog. Luna max readers and workers supplied mappings; the principal owns integration. Review traces authenticated desktop commands, service authority and profile ownership, hidden process lifetime, transient browser data and the localized dialog. Accepted provider-settings, native-agent and desktop-design-system decisions govern; the proposed desktop host ADR is contextual only.

## Findings

### cleanup-owner | high | Retain cleanup authority after native termination failure

Review found that the helper worker originally held its WindowsProcessScope only locally. If termination failed, the attempt could retain a busy flag without handles for a later retry. Corrected: AuthAttempt retains its scope and reader threads, clears the scope only after confirmed termination, and close retries retained cleanup before ownership is released. Wait failure is separately classified so successful containment and reader cleanup can release the attempt. Corrective static review accepted this structure; packaged process evidence is pending.

### development-root | medium | Refuse unmarked source roots before filesystem effects

The initial GUI preparation derived a profile root before checking its development marker. Corrected: marker validation precedes root derivation; focused tests prove no root files are created by refusal. Status also withholds GUI capabilities for an unmarked source root.

### dismissed-revision | medium | Refresh settings when cancellation returns before cleanup

Closing the dialog stopped polling after a single cancel response, which can remain active while URLs are withdrawn and the child exits. Preparation has already committed a new settings revision. The UI worker is correcting dismissal refresh and testing that deferred-cleanup response explicitly. Final evidence pending.

### repository-gate | medium | Unrelated import-quality contract test prevents a green global gate

The required change-scoped test-gate ran its fixed contract population and reported 174 passed, one failed: dev/tests/test_import_quality_gate.py::test_relative_object_module_projection_uses_its_explicit_package_anchor. Its synthetic fixture reports UNRESOLVED_DYNAMIC_TARGET for .dynamic; none of the sign-in files participate in that fixture. See build/windows-x64/provider-auth-test-gate.log. This failure is outside the authorized sign-in change and is not suppressed. The broader check-code gate is still running.

## Recommendations

Current verdict: PENDING verification. Native host unit tests (345), native clippy, 60 package declaration tests, frontend check and 10 provider presentation tests passed before the dismissal correction. The latest protocol/revoked-attempt tests (22) and preparation/revocation tests (10) pass. Registry conformance passes. Finish the corrected UI checks and stable assembled-package lifecycle probes. Human-completed OAuth and a model turn are separate live-account gates and are not claimed by component or fixture evidence.

### corrective-review | low | All scoped findings resolved

The final Luna max static review passes for the sign-in scope. The cleanup owner now also adopts the runtime's unreturned constructor candidate for BaseException, sanitizes worker failures and retains native cleanup authority until confirmed release. The Windows process fault-port contract tests pass (16). Source-root refusal and capability suppression are both in place. Dismissal always refreshes after cancel settles, guarded against profile replacement; the updated UI check and all 11 presentation scenarios pass. Scoped Python verification passes (79), with a subsequent 22-test protocol/attempt rerun after the constructor correction; scoped ruff and ty are clean.

### attended-preparation | low | Allow gateway retirement within the start reply deadline

Principal integration review found the existing native six-second admin deadline was shorter than the service's possible ten-second graceful stop plus ten-second termination. Only connect now receives a bounded sixty-second exchange deadline; status and cancellation remain six seconds. Native static review confirmed no supervisor mutex is held across the wait and service lease/generation checks still fence authority. The real TCP protocol test delays its matching connect reply seven seconds and passes. The three admin tests and native clippy pass; the temporary CMake test filter was restored to empty.

### global-verification | medium | Scoped pass does not establish a clean repository

The full check-code run completed with seven of thirteen gates failed: types, import boundaries, dependency declarations, module reachability, symbol usage, export consumption and docstring references. No sign-in path appeared in those diagnostics. Style, formatting, data formatting and secure-store/persistence/operation checks passed. The required test-gate remains at 174 passed and one unrelated relative-import fixture failure. Registry valid/runtime-load/integrity passed. No global failure was suppressed or changed outside the sign-in scope. The audit remains PENDING overall verification despite scoped review PASS. The stable package rebuild is the last in-scope evidence still running; human OAuth completion and a real model turn are not claimed.

### final-package | low | Stable shipped package passes provider lifecycle checks

The final app-payload build completed successfully after all source corrections. CTest bundle.agent and bundle.provider-auth both passed. Full installed source text matches current service.py, admin.py, auth_attempt.py, auth_protocol.py, agent_provider_catalog.py and the sibling agent provider_auth.py after newline normalization; packaging normalizes checkout CRLF to LF. The final packaged interpreter and installed AuthAttempt initiated real Codex browser and device-code sign-in through the admitted packaged helper. Browser cancellation, device authority loss and a sixteen-second observation lapse each reached browser_action, cancelled, removed transient URL/code and confirmed native process cleanup. The probe emitted event names only, without opening a terminal or logging sign-in data.

S01 and S02 are complete. Scoped review and all focused package/lifecycle checks PASS. S03 and the overall verification verdict remain PENDING solely on the recorded repository-wide failures; these were not suppressed or changed. Human-completed OAuth, saved credentials after completion and a real model turn remain unverified live-account gates. All changes remain uncommitted in Cadrumo feature/tui and the sibling agent main checkout. The built app is build/windows-x64/stage/Debug/app/cadrumo.exe.

### live-desktop | high | Packaged GUI exposed two prerequisite defects

The user's real demo profile could not log in. Runtime evidence identified login_owner_inactive_or_mismatch before password verification. The staged desktop executable lacked the Windows compatibility manifest already present in source because desktop Cargo compilation had no dependency on native_metadata. Added that dependency to Windows desktop build and test targets. Regeneration, app-native assembly, inspection of the staged PE manifest and the actual GUI config.login now pass with the existing profile. Existing Windows login observation tests (2) and native manifest tests (14) pass.

After login, the actual agent panel repeatedly failed desktop_holder_unverified. The Windows desktop intentionally launches its session holder as cadrumo.exe --role runtime, but package generation admitted bin/cadrumo-runtime.exe. Corrected the desktop-session image and digest to the staged Windows desktop role host. The runtime verifier, parent identity checks, descriptor authority and holder scope remain unchanged. A four-case package regression plus two real native verifier tests pass; focused ruff, formatting and ty pass. Luna static review found no issue. Full package assembly and GUI retest are pending. S04 records these additional live prerequisites; previous package helper evidence did not exercise the actual desktop role host.

### live-provider-panel | high | Catalog drift and capability formatting prevented provider setup

Resolved in source: the supplier emits catalog schema 3 with descriptions, structured icons and root icon attribution; the consumer now accepts that exact contract and rejects retired or unknown schemas. Provider status refusals remain one-key envelopes instead of receiving success-only metadata. The packaged catalog now parses 12 provider lanes. Agent-service unit tests pass 329 cases, with 27 integration cases deliberately excluded; 90 focused cases and package bundle.agent plus bundle.provider-auth pass. The actual desktop reaches agent_ready.

The real window then exposed an independent crash: new subagent capability names became undefined labels in Intl.ListFormat and unmounted the React root. Known labels are now mapped, unknown future proofs omitted, and generation-scoped proofs excluded from lane-wide summaries. All newly consumed sign-in and capability translation keys are declared in the desktop chrome projection. The frontend check, 11 catalog regression tests, and 20 canonical locale/projection tests pass. Final Luna static review found no defects in these changes, Windows holder identity, or manifest ordering. Normal rebuilt-window verification remains pending.

### debug-storage-location | high | Verification launch placed private provider runtime inside Git

The principal's disposable GUI launch explicitly selected a storage root beneath build/windows-x64/testing/Debug/provider-sign-in-live. A user-started model turn correctly refused its derived Codex runtime workspace under Git. This was an incorrect verification environment, not a reason to weaken provider isolation or redirect only temporary provider homes. The documented manual complete-root relocation preserves profile data, keystore and agent root identity; native automation and sign-in receipts may require reauthentication after relocation. The stopped debug root was relocated to the external LocalAppData/cadrumo-provider-sign-in-dev directory. File count and total bytes match before and after relocation; the original storage path is retired. A local build-directory launcher pins this development root and refuses Git ancestry. Normal user storage was not changed. Rebuild and post-relocation GUI verification are pending.

### relocated-desktop-verification | low | Normal packaged GUI works from external debug storage

The final app-payload build passed and the assembled bundle.agent and bundle.provider-auth tests both passed. The normal packaged executable, without remote debugging or the page-only ListFormat bypass, opened the retained demo profile and reached agent_ready. Actual GUI inspection confirmed provider controls and translated Iniciar sesion wording. A minimal prompt submitted through the GUI selected Codex/gpt-5.5, created its isolated runtime under LocalAppData/cadrumo-provider-sign-in-dev/agent/<profile>/home/tmp/homes, and reached Codex turn started. The window received a close request before the turn completed, so this is startup/path evidence only, not completed model-work proof. The provider home had no auth.json; completed provider sign-in and credential persistence are still not claimed.

Manual relocation required a separate runtime identity recovery. The displaced .runtime/installation.json retained its old storage identity; status translated that refusal to unknown, blocking the startup readiness gate, while authenticated logout exposed runtime_root_mismatch. With all package processes stopped, the old nonsecret record was archived outside .runtime without modification. Normal profile admission then generated a fresh root-bound installation identity. Password-assisted production config logout succeeded, followed by a successful actual GUI password login. Profile, keystore and agent identity files were retained. A new installation creates new automation and sign-in bindings; old automation grants are not adopted. This repair is confined to the disposable development environment, not a change to identity verification.

S04 prerequisite repairs and scoped static review pass. S03 remains open for the previously recorded repository gate failures and uncompleted live-account/model-turn evidence. The window is closed. Repeat verification uses the local build/windows-x64/launch-provider-sign-in-dev.ps1 launcher, which selects an external debug data root and refuses Git ancestry. Direct launches do not inherit that script's development override.

### normal-launch-sign-in-review | medium | Retry callbacks and input validation need correction

Independent integrated S05 review found that delayed cancel/browser-opening responses could overwrite a newer retry in ProviderSignInDialog.tsx; bind these callbacks to the originating attempt and generation. The supplier Claude relay must reject non-ASCII nonces without an unhandled task exception. Supplier URL validation must preserve blank query values and reject duplicate or mixed-case code flags consistently with host validation. The installed Claude probe must fail explicitly when the relay prerequisite is missing instead of skipping. The principal assigned these corrections to the owning workers. No additional defects were found in method metadata, executable discovery or native relay dispatch.

Verdict remains PENDING. Component evidence covers 338 service tests, 26 final protocol tests, supplier auth tests and installed Claude initiation/cancel, frontend checks and provider scenarios, and the platform resolver. Packaged rebuild/probes, final changed-behavior review, human OAuth completion and completed real model work remain outstanding. Initiation and cleanup do not prove authentication or model capability.

### live-sign-in-repair-final | low | Source and packaged initiation checks pass

Verdict: PASS for S05 source and packaged initiation/cleanup scope. The independent reviewer rechecked all reported findings: generation-bound UI retries, nonce rejection, consistent query handling, explicit missing-prerequisite failures and the native executable slot are resolved. The host supplies the browser relay only during GUI auth; ordinary agent prefix admission remains unchanged.

The final native_contract plus app-payload build passed. Native host unit checks passed 351 tests with Clippy; the final platform resolver check passed after adding the typed browser executable slot. Frontend checks passed, and both deferred-response regressions passed. The final package passed bundle.agent and bundle.provider-auth. The offline missing-provider fixture initially failed installed_base_unavailable after isolating USERPROFILE; setting the canonical storage-root override only for that temporary fixture corrected its setup without changing production behavior.

All six installed-provider probes passed through the assembled package with no external-bin override: Codex browser cancel and observation-loss cleanup, Codex device revocation cleanup, and Claude browser cancel, revocation and observation-loss cleanup. These use the packaged native browser relay and external disposable homes. They establish login initiation and cleanup, not completed OAuth or model capability.

The normal GUI was reopened without storage or executable-path overrides and reached the local sign-in screen for Test Profile. The owner was asked to authenticate in the app. S03 remains PENDING for attended application verification, completed provider OAuth and a completed real model turn, alongside its previously recorded repository-gate gaps. No credentials were copied or recorded, and no commit or push was made.
### sign-in-completion-recovery | low | Integrated source review passes; live recovery remains pending

The owner completed Codex browser authentication in the normal packaged GUI. The service recorded provider sign-in succeeded with cleanup_confirmed=True at 2026-10-17T22:01:37.325Z. This proves provider sign-in, not a completed agent turn. The earlier agent_service_failed event came from the intentional agent retirement before sign-in; the service had no terminal-auth resume path.

S06 repairs the completion dialog, neutral treatment of agent_retired while retaining the admin endpoint, and one-shot agent resume through the existing observation loop after auth cleanup. Resume requires the original profile/session/settings authority to remain current. Unexpected outer service exit still produces a failure and retry. Stored provider-sign-in selection is shown as not verified rather than requiring sign-in unconditionally.

Independent integrated source review passed. The service suite passed 346 tests; four focused resume tests passed. Native unit tests passed 353 tests and Clippy passed. Frontend checks, locale generation and the focused success presentation scenario passed. The rebuilt package and live recovered-gateway/model response remain pending; S06 and S03 remain open. No real-turn capability claim is made.

### provider-ui-simplification | low | Source review and focused browser checks pass; packaged verification pending

S07 groups provider connections beneath searchable expandable provider rows, uses the admitted wheel's validated artwork, and replaces internal status and error wording with actionable messages in English, Spanish, Catalan and Hungarian. Each connection remains separately configurable. Configured describes saved credentials or observed sign-in, not proven agent capability. Unknown sign-in remains Not checked. The picker retains unavailable connections with explanations and prevents selecting them.

Independent integrated source review found two accessibility issues in the searchable picker. Both are resolved: Radix owns the trigger/dialog relationship, localized labels name cmdk controls, and the trigger announces the selected provider and connection. The final three-spec browser run passed 56 cases; frontend type, lint and formatting checks passed. Icon generation passed eight focused tests, Ruff and ty, and the real CMake icon target; canonical chrome tests passed 20 cases. The frontend and desktop host compiled successfully.

Visual review then found long Spanish badges squeezing the provider name into one letter per line. The summary now places icon/name/caret together and badges in a separate full-width row. Independent review of this correction and the new Spanish/Hungarian geometry assertions found no further issue. Execution of those final regressions and refreshed screenshots is pending at this checkpoint.

A separate lifecycle-test session continues using the shared staged app. Package replacement is held. The desktop-host-build dependency unexpectedly invoked native-process-quiesce, which reported stopping three package identities during that external test; affected external test evidence may need rerunning. S07 remains open pending final visual and packaged verification. S06 and S03 retain their previously recorded live recovery/model-turn gaps.
### provider-ui-simplification-final | low | UI verification and rebuilt package pass

Verdict: PASS for S07. The final two-row correction passed frontend checks and both Spanish/Hungarian narrow-layout geometry tests. Principal visual inspection confirmed readable names, aligned expand controls, wrapped status labels, visible Codex artwork and a searchable picker with an unavailable connection explanation. Screenshots are under build/windows-x64/desktop/provider-ui-review (provider-settings-collapsed.png, provider-settings-expanded.png, provider-picker-search.png, provider-settings-es-narrow.png and provider-settings-hu-narrow.png). These are presentation evidence, not provider capability evidence. The preceding broader provider/picker/agent run passed 56 scenarios; unchanged behaviors were not rerun after the layout-only correction. Temporary capture code was removed.

The external lifecycle test exited before package replacement. The app-payload build completed with exit 0, and bundle.agent plus bundle.provider-auth both passed through the assembled package. The normal app was reopened without storage or executable overrides and displayed its local profile sign-in screen. The owner was asked to sign in inside the app. S07 is closed; S06 and S03 remain open for attended recovery and completed model-turn proof. No commit or push was made.
### S08 authentication failure presentation review

PASS. Authentication failures use existing localized sign-in guidance and an enabled Agent settings action; raw backend failure_reason text is no longer appended. Unknown conditions fall back to the generic localized failure. The authentication case omits disabled Retry. Frontend checks and four focused browser scenarios pass; canonical chrome projection passes 20 checks. Normal Debug app-payload build and assembled bundle.agent and bundle.provider-auth checks pass. The actual upgraded profile accepted a fresh Claude/haiku run r8a1fd5f920c73eb93041ef50 which failed Authentication required and settled failed/inactive, followed by provider settings and Sign in to Claude dialog. This establishes live refusal settlement, not a completed model turn. S08 is closed; historical real-model gates remain open. The subsequent transient unlock startup diagnostics request is tracked separately by event-relay-recovery S04 in the supplier worktree.
