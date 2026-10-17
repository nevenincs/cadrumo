---
tags:
  - '#audit'
  - '#provider-sign-in'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:0f77ba993d144b702ec761884d0ce1c0336bdfac11966932eed964eeba086b45'
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
