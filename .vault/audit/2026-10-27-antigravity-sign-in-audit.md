---
tags:
  - '#audit'
  - '#antigravity-sign-in'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:f2fda1208a78d4c08c70d4c802648a227a66748b7ad3bd25df586ad30226701d'
related:
  - "[[2026-10-27-antigravity-sign-in-plan]]"
---

# `antigravity-sign-in` audit: `Isolated provider code submission and integration verification`

## Scope

Uncommitted S01 and S02 changes in the tui worktree under the approved plan. Independent architectural review traced discovered capability, transient browser action, raw Tauri body, separate secret administration frame, exact-profile attempt ownership and helper stdin. Existing unrelated modifications are outside this review. The brief prohibits commits and pushes.

## Findings

### terminal-submission-race | medium | Resolved by atomic terminal withdrawal

Review found a submission window between parsing a terminal helper event and withdrawing code-entry state. `src/cadrumo_agent_service/host/auth_attempt.py` now performs both under its submission lock. Deterministic concurrent-submission coverage and deadline/watchdog boundary tests passed in the 37-test focused rerun; the final eight-file Python run passed 134 tests.

### refused-code-submission | medium | Resolved with explicit retry after cancellation

Review found that a refused or unknown submission could consume the UI opportunity while the helper still awaited a code. `native/desktop/frontend/src/components/settings/ProviderSignInDialog.tsx` now clears transient input, cancels the original attempt and requires an explicit fresh-attempt retry. Encoded helper-line size is checked before submission. All 26 provider browser scenarios passed, including coalesced browser action, cancellation, refusal recovery and escaped-length refusal. The complete frontend check passed.

### credential-custody | low | No remaining issue found in changed interactions

The new human-only administration action keeps code bytes outside metadata, status snapshots, diagnostics and model-facing operations. Helper writes serialize with cancellation; current attempt and profile/login/settings generations are checked. The validated URL survives the immediate code-required event and is withdrawn on submission or settlement. Provider-specific OAuth and credential storage remain in the supplier. The additional gateway-versus-parent administration authority test passed all 30 cases.

### verification-prerequisites | low | Review pending package and attended live evidence

Verdict PENDING. Registry validity, runtime load and integrity passed. Full repository code, locale, scoped test gate and CMake native/package checks are still running at this checkpoint. The matching agent working tree produced wheel version 0.1.0 with SHA256 e5bb53a8970a7a3547e443fe73f258536f666393b539c9ec54dd771dd65e870e; no assembled-package claim follows from the wheel alone. No completed fresh Google OAuth or same-profile model turn was performed. The user clarified that an authenticated account is unavailable in this development setup; no login data is requested or received. Provider quotas were reported exhausted by the supplier owner. Concurrent-child and final supplier child-cancellation limitations in the brief remain unresolved.

### stream-failure-submission-race | medium | Resolved by atomic malformed-event and EOF invalidation

Final review found that malformed events and stdout EOF could release the parsing lock before retiring code-entry state. The same submission lock now withdraws that state and sets cancellation on parser failure, including EOF, before the exception propagates. Deterministic overlap regressions passed; the final eight-file Python suite passed 137 tests. The final package is being rebuilt after this correction.

### deterministic-check-results | low | Feature checks pass while broader repository gates remain blocked

The native backend unit target passed 594 tests, with one existing subprocess fixture ignored. All 26 provider browser scenarios, the complete frontend check, registry validity/runtime-load/integrity, and the fresh full type check passed. Initial check-code exited 1: its transient type diagnostics subsequently passed, while import authority failed because governed sources changed during the run. The separate import-boundary rerun exited 7 for the same source-churn condition: all 30 contracts were kept and all 4948 modules loaded, with zero hard findings. The scoped test-gate entered its CI contract population and exited 1 with 1172 passed and three failures outside sign-in: platform recipe parity, instrumented ledger-worker bootstrap, and ambient temporary writes in browser archive/modelo fixture tooling. Check-locales exited 1 with existing inventory/translation findings; neither findings nor backlog contained the three new sign-in keys. Full native host-test attempts were refused twice when unrelated production sources changed during documentation compilation. A local development package is being assembled with the supported user-documentation omission; the shared cache setting will be restored. The broader bundle run was intentionally interrupted after app assembly when it entered MSI generation; no completed bundle/MSI claim is made.

### native-helper-admission | medium | Resolved exact browser-code launch declaration

The first actual packaged probe failed before helper ready: native invocation_undeclared, exit 125. The native environment declaration admitted browser and device but omitted browser-code. `native/application-environment.toml` now admits the same private agent-auth invocation with identifier-bounded provider, literal browser-code and exact timeout 300. Windows/POSIX admission and refusal vectors preserve environment scrubbing. Declaration/image tests passed 68 cases and full launch-vector replay passed 111 cases. The rebuilt native policy then passed the real helper smoke.

### final-payload-evidence | low | Pinned package passes isolated real helper and conformance checks

Selected local Windows Debug application payload: `build/windows-x64/stage/Debug/app`, version `0.6.0+2026102726.debug`, manifest SHA256 fd6ab1bac5c24e3bd1b03898f7c44461aedf13c22788e5ab6b2fc1edcc785e69. Agent version 0.1.0, wheel SHA256 83941348cd70768a772af228f59e43618b6f00d6a9e5a227e7a1874994e32cf5, pinned to published supplier commit 74bcf66c3bd054ff6067cdc21ebc779f927af387. All 491 packaged supplier Python files match that commit after normalizing Windows line endings; five deployed application auth modules match the final source bytes and package inventory. `final-package-identity.json` below the feature temporary directory records this identity. Supplier main subsequently advanced into unrelated and unfinished proof/runtime work; the source owner confirmed no known Antigravity-auth invalidity in the selected commit and endorsed retaining the immutable tested payload.

Real Antigravity CLI 1.4.8 packaged smoke passed two independent fresh signed-out statuses, GUI capability schema 3, browser-code code-required state with retained validated URL, cancel, authority revocation, lost-dialog watchdog, and synthetic invalid-code submission followed by cancellation. Whole owned process cleanup was confirmed for all four attempts. No account credentials or model prompt were used. This proves initiation/submission/cancellation, not completed OAuth or a model turn. Packaged agent and environment-conformance CTest checks both passed; native Clippy and scoped Rust formatting passed. The development payload intentionally omits bundled user documentation; the original shared CMake user-docs ON setting and original supplier source-directory selection were restored/preserved. The full bundle/MSI run was interrupted during distribution generation and is not claimed complete.

### final-review-verdict | low | No remaining implementation finding; overall evidence pending

Independent final review found no remaining issue in terminal/malformed/EOF submission invalidation or the narrow native launch authorization. Source verification includes Python 137 passed, frontend provider scenarios 26 passed and complete frontend check, native backend unit tests 594 passed, declaration/image 68 passed, vectors 111 passed, native Clippy, scoped formatting/types, registry validity/runtime-load/integrity, and the actual packaged checks above. The latest full type rerun reports three missing-argument diagnostics in unrelated runtime cleanup tests; earlier transient feature typing diagnostics are resolved and scoped final checks pass. Broader test/locales/import-authority failures recorded above remain outstanding. Overall PENDING and S03 stays open for completed fresh OAuth, same-profile model turn, remaining supplier parity proofs, and clean broader gates. Cadrumo main was not edited by this work; no app commit, push, reset or unrelated cleanup was performed.

### silent-code-entry-repair | high | Source transport corrected; packaged successful login remains pending

The user's live report invalidated initiation-and-cancel evidence as proof of usable code submission. Installed agy 1.4.8, SHA256 074c7b99b7727dcd2c7437973454d0856181a1006c97a4fad91a1ed23c10ad44, stayed silent after synthetic invalid input through a pipe; the same isolated invocation through a pseudoconsole immediately returned a provider error. The user authorized extending the repair into Y:/code/cadrumo-agent-worktrees/main. Its private authentication adapter now uses native Windows ConPTY, with suspended creation, exact retained-handle Job admission before resume, bounded private output and terminal Enter input. Explicit null standard handles prevent redirected helper streams being duplicated into the provider; cursor-row transitions are preserved before escape removal. Provider result errors terminate the helper rather than remaining progress. The profile status probe recognizes the absent isolated credential source without a cold CLI launch and recognizes the current code prompt as signed-out evidence.

The app dialog now shows localized checking-code progress, including after stale code-required observations, and the new scenario checks transition to explicit failure and retry. Supplier focused regression run passed 60 tests, including the real installed invalid-code and cancellation cases plus containment; the final terminal/installed regression rerun passed four tests after constructor-failure and cleanup review. Scoped supplier Ruff, formatting and ty passed. App service private-code tests passed 39; four browser-code UI scenarios passed. Frontend TypeScript, ESLint and 23 node checks passed as part of npm run check, which exited 1 on four unrelated formatting files. The broader provider scenario run was invalidated by concurrent removal of generated chrome strings; the focused rerun passed after regeneration. No new code or account credentials were entered through chat, no model turn was made, and neither a rebuilt Debug application nor successful OAuth/token persistence is claimed. Verdict PENDING for S03 live/package evidence; the source transport regression is resolved.

## Recommendations

Leave S03 open for completed fresh app OAuth, a same-profile model turn, remaining supplier parity evidence and clean broader gates. Retain the identified immutable tested package rather than ingesting concurrent unfinished supplier changes. Authentication codes remain in the app-owned private input path; no account credentials are requested through chat.
