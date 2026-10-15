---
tags:
  - '#audit'
  - '#language-sync'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:a0989b802916312f3279f57039d1a99772a32cb11a852116903b29c336dfe209'
related:
  - "[[2026-10-15-language-sync-plan]]"
---
# `language-sync` audit: `Shared language propagation and state preservation review`

## Scope

Integrated review of S01-S03 of `2026-10-15-language-sync-plan`, including uncommitted Python/runtime/client/TUI, Rust host, frontend and documentation bridge changes. Unrelated pre-existing worktree edits are excluded. The accepted desktop decisions' language exceptions retain authenticated canonical profile writes, exact connection scope and catalog authority.

## Findings

### retry-stranded-tui | high | A transient canonical read failure could strand the old language

The first implementation returned from `src/cadrumo/entrypoints/tui/app.py` after one failed canonical read, while the runtime coalesced the unchanged hint. The corrected candidate retains pending invalidation and failed screen owners, retries with a capped interval, fences binding identity and cancels on retirement/unmount. The root-event test injects the first failure and exercises the subscribed app path. Final verification remains pending.

### financial-draft-locale | high | Rewording an open numeric editor could reinterpret its existing lexeme

The first `CasillaEditorPanel.refresh_language` changed its parser locale while retaining the raw draft. The corrected candidate pins the entry locale for that editor's lifetime and independently updates display copy; an ambiguous-number test retains the same input and typed value after switching language and editing again. Staged typed edits retain their original concurrency witness. Final verification remains pending.

### preserved-admission | medium | Relocalization must not silently renew a staged edit baseline

`InstalledModeloWorkbench.load` owns a new admission and is unsuitable for a language repaint. The candidate adds a separate translation read that never assigns its held `_state`, compares edit coordinates and complete form facts, and refuses changed or unprovable source state. Readonly forms receive equivalent fact comparisons. Tests cover retained admission identity and changed-head/value refusal. Final verification remains pending.

### native-test-scope | medium | The first integration fixture did not satisfy desktop peer admission

Opening a DESKTOP projection directly from pytest correctly produced `runtime_peer_untrusted`. The fixture now uses admitted CLI/TUI connections and real registered profile mutations, verifies encrypted persistence and foreign-profile isolation, and drains the observer's initial invalidation before the change. Actual Rust host verification remains separately required; the fixture grants no desktop role and weakens no admission rule.

### frontend-fixture-lifetime | medium | StrictMode could expose a discarded scenario host's language controls

The first development-only fixture published its controls during constructor execution. The candidate registers them from the active observation subscription with identity-checked cleanup. Browser tests exercise external updates, older revisions, delayed replies across accounts, refused writes and operation without documentation. The palette's second combobox requires explicit accessible selectors in existing keyboard assertions.

### inherited-language-precedence | high | Inherited defaults could hide a newly selected profile language

The installed interactive TUI previously retained environment/settings precedence over the saved profile choice, so an acknowledged switch could leave its renderer unchanged. The corrected candidate enters a scoped profile-preference precedence context for the installed TUI lifetime, including renderer cache identity, and adopts the authenticated canonical preference before composing its root. Standalone CLI invocation precedence remains unchanged. The environment-precedence regression set passed 40 tests.

### captured-backend-language | high | Future pane reads could keep using the startup language

The installed initial/workbench roots passed a captured startup language into explicit backend reads after the renderer snapshot changed. The corrected owners accept the canonical refresh callback off the UI loop, snapshot language and an epoch for each read generation, invalidate the initial Home cache, and refuse stale generations without retiring the session. Fresh profile overview data is cached for future screens without replacing a mounted editor's witness. The new locale-capture and adjacent root/account-factory tests passed 18 tests.

### obsolete-layout-language | medium | Old desktop layouts could retain a competing language field

The first frontend candidate ignored the obsolete saved `prefs.language` while leaving it in localStorage until a later layout save. The corrected loader removes that one obsolete field immediately while preserving the remaining stored layout and settings. The current production-bundle scenario still requires a fresh build and rerun; the earlier bundle predates the correction.

### corrective-review-closure | low | Earlier high findings have passing corrective evidence

The stable candidate resolves retry-stranded-tui, financial-draft-locale, preserved-admission, inherited-language-precedence and captured-backend-language. The installed root and adjacent factory tests passed 18 cases after the final cache-helper extraction; the live refresh file passed 10 cases, including a real Home factory swap during an overlapping refresh. Worker cleanup now releases by epoch and retains pending work for the replacement factory. Numeric drafts keep their entry language and the existing edit witness; relocalization never replaces the held admission. The initial 40 environment-precedence cases remain passing evidence.

### held-auth-and-external-filing | medium | Mounted and future backend reads must both follow the canonical locale

The held AEAT authentication door now resolves the current renderer language for each read, pins it around the backend call, and refuses a profile or locale change during that call. Its adjacent profile/authentication set passed 17 cases. ExternalFilingDetails needed missing localized imports and an in-place held-summary repaint; its current integration file passed 17 cases, covering disclosure, selected row and focus preservation. These corrections do not reopen or replace a staged write baseline.

### frontend-and-native-verification | low | Stable frontend and native adapter have passing scoped coverage

The corrected current frontend passed npm run check. The configured full browser suite collected 593 IDs: 544 passed initially, 47 of the remaining 49 passed on the first fresh retry, and the final two setup/teardown timeouts passed with one worker. Every collected ID therefore has passing evidence, without a claim that one uninterrupted suite passed. The documentation bridge full file passed 35 cases and failed one duplicate-anchor assertion; that corrected case passed in its focused real-browser retry. This also verifies the obsolete layout language field is removed immediately. CMake-owned Release verification passed 335 host unit tests, clippy with warnings denied, and the final executable build with the current frontend. Direct rustfmt check passed for the five owned Rust files. No packaged GUI end-to-end acceptance is claimed.

### live-log-tail-verification | medium | A separate production log-tail test remains failing with unknown provenance

The real_rotation_across_processes_while_tailing live-package test failed again through the supported CMake Release target: zero matching records were collected during rotation, while a later settled Tail read found records. The direct fixture creates Tail, launches Python log writers, and bypasses all five language adapter files, Person::hold and session hold. The environment projection participates in setup. Static tracing supplies no baseline or cause attribution; this is retained as an unresolved log-reader verification result rather than described as an established pre-existing failure.

### propagation-limits | low | Cross-process language refresh has bounded observation and failure-path limits

The desktop observes the canonical holder approximately every two seconds; the runtime hint observer coalesces invalidation at at most two reads per second. Canonical profile persistence remains authoritative and notifications carry connection coordinates rather than an authoritative language value. If a canonical write succeeds but the best-effort nonsecret hint mirror fails, other processes can remain stale until a later hint update or rebind. A built-in Textual command palette already open during a change can retain its original placeholder/provider copy until reopened. Signed-out desktop choices remain transient; explicit CLI flags/settings remain invocation-local while later ordinary CLI defaults follow the profile preference.

### cached-account-observation | low | Final profile-scoped frontend correction passes

Luna's final read-only review found the native observer could initially replay a cached value belonging to the previous account, and the frontend could keep a prior failure alert after recovery. The corrected controller accepts only the typed current account profile, hides old identity state before subscription effects run, and preserves revision ordering and delayed-write generation fences. A newer accepted observation clears a failure; stale, equal-revision and wrong-profile observations do not clear it. The final npm run check and all six focused language scenarios passed. The real hostless browser mode remains no-host and accepts its transient profile-null choice. This resolves the finding without changing native authority or introducing another store.

### configured-python-gates | medium | Required repository verification remains incomplete

The current 93 changed Python files pass configured Ruff lint and format checks. The full configured type runner exits zero with ten advisory diagnostics, all outside the 130-path feature manifest. The change-scoped parallel lane has passing evidence for all 175 collected IDs across the interrupted current run (147) and its exact resumed remainder (28); its serial lane selected no tests. The pytest harness gate passed four cases. Earlier focused language, environment-precedence and backend/current-screen sets retain applicable passing evidence as described above.

The fresh import-boundary gate fails after current generated module enrollment: 1,144 hard findings (1,143 PRIVATE_CROSS_PACKAGE and one UNRESOLVED_DYNAMIC_TARGET), 324 new unapproved ratchet occurrences and 110 shipped-root occurrences reaching repository-only roots. All 4,790 governed modules loaded. Its 424 candidate occurrences intersect no manifest path; inspection of all 93 Python diffs found no added private import target or dynamic-import construct. Only the ten highest hard-finding source locations survive in the report and none intersects the manifest; the other 68 locations are truncated, so complete nonintersection is not claimed. The three other current static reports also fail: module reachability lists one custody credential module, symbol usage lists 15 files, and export consumption lists 11 files; those reported paths have no feature-manifest intersection. These checks remain failures, not accepted green evidence.

Sequence goldens refuse the stale .authority/authority.current.json descriptor after legal-source edits in the shared worktree. The language implementation does not publish registry authority or repair other workstreams' source. Current durable artifacts are in var/storage/development/.logs/test-runs/2026-10-15, including the import-boundary run 20261015T124438.516996Z-check-import-boundaries-51788-44b840c5 and the resumed 28-case run 20261015T123722.310526Z-pytest-42584-7d84189e. Scoped final Ruff/type/CI logs are also preserved under the user's TEMP folder with the cadrumo-language-sync prefix.

### final-integrated-verdict | medium | PENDING repository gates; no unresolved critical or high language defect

The review reuses prior integrated and corrective reviews plus Luna's final stable frontend review. Canonical encrypted persistence, authenticated mutation, exact-profile/session invalidation, scoped renderer precedence, held backend locale reads, in-place mounted presentation, documentation navigation and stale-account handling are implemented. The reviewed native adapter is committed as 29426604d8 and the backend checkpoint as d729dfb81f; final frontend changes are the stable reviewed working-tree candidate. S01 remains open because required repository-wide verification has not passed. S02 has passing scoped native checks; S03 has passing current frontend/docs coverage. The separate live log-tail failure and the explicit propagation limitations above remain recorded. This is not a completed-plan or packaged-GUI acceptance claim.

### final-ci-and-release-evidence | low | Corrected CI node and embedded frontend have passing fresh evidence

The final CI contracts wrapper passed 1,136 tests and failed one collect-only child because a temporary documentation root no longer existed. The exact failing node, test_harness_member_preflight_rejects_empty_collection_even_when_another_member_exists, passed on a fresh isolated retry with the original CI marker and unchanged source and environment. Its durable retry run is 20261015T130604.807126Z-pytest-64008-ab77f37b. The configured separate serial recipe returned zero with no selected serial cases. All 1,137 CI test IDs therefore have passing evidence across these runs; the original wrapper's nonzero exit is retained. The CI docs build completed with the existing missing api/index reference warning.

After the last frontend correction, the official CMake desktop-host-build Release target passed again and rebuilt the current frontend bundle into build/desktop-windows-x64/cargo/desktop/release/cadrumo.exe. The current npm check, six language scenarios and Release build logs are preserved in TEMP under the cadrumo-language-sync prefix. Feature-scoped vault checks for language-sync and all three amended desktop decision features found no errors in the changed records. This fresh evidence supplements, rather than replaces, the earlier review and failure history.

## Recommendations

Keep the existing profile fact and catalog definitions as authorities. Notifications remain nonsecret invalidation cues and background reads must never report person activity. Complete focused and configured verification, review the stable candidate and append the final verdict before closing the plan. No additional architecture decision is recommended for the corrected implementation.
