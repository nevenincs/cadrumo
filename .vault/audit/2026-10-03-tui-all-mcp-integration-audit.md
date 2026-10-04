---
tags:
  - '#audit'
  - '#tui-all-mcp-integration'
date: '2026-10-03'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:ade6930cea13588e021fd1e879c77d36071d31422b0f9f2a30498d7a487418f3'
related:
  - "[[2026-10-03-tui-all-mcp-integration-plan]]"
---
# `tui-all-mcp-integration` audit: MCP recovery and combined runtime behavior

## Scope

Review the original-base deltas of all six preserved MCP worktrees, the collision scratch lineage and conflict-stage evidence, and later relevant TUI work in the isolated integration branch. The user authorized implementation, routine conflict resolution, verification and safe landing. The original worktrees and their indexes remain untouched by the integration. Accepted runtime decisions require transient session-owned containment and preserve the current runtime-mediated CLI/TUI admission boundary.

The source inventory contains 3,069 original source/path deltas. The disposition corpus accounts for every pair and also records selected later TUI captures, excluded transaction locks, and unrelated active-writer paths preserved outside this MCP scope. A disposition is an intent assessment with an original base, source snapshot, source-delta hash, replacement and reason; mechanical equality alone is not the semantic decision. Integration commit mappings are finalized after coherent checkpoints.

## Findings

### stale-coalition | high | Orphan cleanup could lose custody when a transient launchd job disappeared

Resolved. `src/cadrumo/adapters/local_runtime/macos_worker_process.py` now reaps the saved coalition even when launchd no longer lists its job, and retains its marker/refuses replacement when verified termination fails. Independent orphan and failed-termination tests cover the custody invariant. Native Darwin containment exercises parent, guardian and worker loss, browser descendants, setsid/regroup escape, registration loss, churn and stale-job recovery: eleven tests passed. A final shared-process fixture rerun passed two tests; unchanged containment code permits reuse of that evidence.

### darwin-worker-admission | high | Native worker routing and explicit authority controls were missing

Resolved. Darwin now selects the POSIX worker endpoint. Worker and guardian environment construction preserves the declared storage, authority and temporary path controls while excluding ambient credentials and interpreter injection. Actual native startup diagnostics established the missing authority cause before the correction. The final native containment run passed after a verified source overlay; Windows portable checks were not substituted for Darwin behavior.

### historical-collision | high | Trial markers and obsolete resolutions cannot govern the recovered product

Resolved through per-path disposition. The collision trial, scratch parent and conflict-stage refs remain immutable evidence. Conflict-marker files were rejected; newer runtime, registry, typed authority and CLI owners supersede obsolete trial code where recorded. The earlier binding-consumer plan was recovered from its latest actual historical blob through the owning CLI, retaining its original twelve Steps and six completed Steps. Ten omitted historical purpose-authentication ledger rows were restored through the ledger CLI; those rows preserve history and do not reinstate runtime administration.

### canonical-imports | medium | Captured callers depended on removed forwarding and private defining surfaces

Resolved source changes use direct public defining imports, including the CLI parameter/shared contract modules, test enrollment recipient and codec/parser helpers. The root fixture owns the outward runtime composition dependency so the shipped harness remains inward-only. The configured import checker initially found two unresolved dynamic loops because a shared lexical variable accumulated all four bounded root sets; separate lexical bindings fix the actual resolver without changing its cap or contract scope. The subsequent configured run reported zero hard findings and loaded all 4,359 targets, but correctly refused a final verdict because test files changed during the run. A stable rerun remains required.

### native-keychain-context | medium | Protected verification requires an unlocked native login security session

Resolved verification dependency. The original locked native context correctly returned NEEDS_USER. With explicit user authorization, a masked askpass prompt on the Mac delivered the password directly to the native unlock API, without a credential in chat, arguments, environment, files or tool output. Unlock and tests ran in the same SSH security session. Three native namespace round trips passed, each replacing, reopening from a fresh process and deleting binary items; the mutually exclusive locked-context detector skipped. No Keychain provider or access policy was weakened.

### executor-scenario-coverage | medium | The combined registered-operation matrix lacked concrete scenarios

Open verification repair. The broad affected suite exposed 57 registered operations absent from its independent expectation families. Workers are adding actual registered-handler scenarios with concrete result, effect, phase and cleanup assertions; the matrix is not narrowed or suppressed. A human-facing private ledger refusal test also lacked runtime admission and was moved to its existing native CLI fixture while retaining its original assertions. Missing browser provisioning was an environment prerequisite; the public provisioning command installed the required Chromium build and the controlled category path is explicit for reruns.

### installed-withholding | medium | The new installed continuation failed during public CLI seeding

Open diagnosis. The recovered continuation keeps the current withholding capture route unavailable and uses public CLI input capture followed by actual installed runtime TUI calculation, verification, export, local recording and fresh-process reopen. Its independent export and admission assertions passed eleven focused tests. The first fresh-wheel native journey failed before reaching TUI and retained a failed receipt. The receipt initially discarded the typed CLI failure stage, so the owner is repairing the sanitized diagnostic evidence before identifying and fixing the concrete cause. This is not a demonstrated production defect until its cause is established, and no end-to-end success is claimed.

### current-registry-generation | medium | Later M190 and M390 changes alter real typed export geometry

The selected later TUI source and mapping deltas preserve typed perceptor rows, the complete M390 filing envelope, source pins and current public codec APIs. They are semantic data changes, unlike the earlier provenance-only digest edits. Canonical authority publication passed locally and on Darwin with the same logical identity `5375497a63086b77cb673bf468f370ea944af86f6892190132b5e67bc2bc3308`. Fresh bounded committed-render comparison and installed export behavior remain required to finalize that proof.

### active-destination | medium | The live TUI writer prevents an uncoordinated checkout update

Open landing dependency. Later committed calendar, filing-session and native application changes were reconciled alongside the selected dirty source deltas. Unrelated desktop and active documentation work is preserved separately. Before landing, inspect the destination's latest commits and relevant edits again and reconcile any new changes. Do not reset, clean, stash, switch or overwrite the writer's checkout. The isolated integration branch has not been described as landed.

### preview-projection | low | Framework sync preview did not fully describe adoption changes

Observed during canonical rule projection. The owning sync command's preview reported no file changes while describing adoption state; the applied isolated sync updated the rule projections and provider state. The rule prose now derives the public MCP tools from the typed protocol and names corpus/ranked discovery. No broad pending framework migration was applied.

### later-tui-cut | low | New runtime, filing and packaging changes are reconciled in the isolated baseline

Resolved source reconciliation. Merge checkpoint 4d3455f47d incorporates immutable destination cut a8a7fb7d26 after 60c063bba1. Six application/TUI and eighteen native/packaging conflicts preserve current public typed ownership alongside newer filing captures, retained error origins, shared approval prompts, published-generation refusals and Windows artifact identity controls. All 106 incoming cut paths have dispositions: 75 incorporated, 25 already present, and six superseded by recorded current public/guard repairs. Focused static checks and three packaging regressions pass. Historical source and artifact evidence remains scoped; this does not establish final combined E2E success or landing.

### affected-test-expectations | medium | Fresh replay identifies stale M347 and browser fixture expectations

Open bounded verification repair. The first fresh affected batch completes 291 passing tests and three failures. Two M347 failures use an expected binding set that predates province/lease row metadata; independent fixed-width export scenarios pass. The browser negative fixture changes a legacy environment variable while the declared canonical browser category remains configured, so its purported empty cache is not selected. The owner will correct those independent test premises and replay the affected cases. No production regression is established by these three failures.

### native-replay | low | On-device masked unlock enables a fresh native cohort and installed artifact proof

Fourteen actual Darwin containment/peer/Keychain tests pass after a masked askpass prompt in the same SSH security session; one mutually exclusive locked-context detector is excluded when the Keychain is unlocked. The current final-cut wheel matches all 3,220 production modules and its embedded authority. Native installation verifies exact site-packages bytes and logical authority c057cec11d240befcd95e3567a800e0c0581f132bd76b88f1c1e43dc2191c12c. Runtime source changed in the later cut, so its owning native cohort is rerun rather than inferred from prior results. Actual installed MCP and seven-work/two-child withholding E2E are running and remain unproven until their receipts pass.

### original-source-reobservation | low | All six original MCP worktrees have no later source deltas

Resolved preservation check. A fresh six-source alternate-index observation records zero source deltas, zero capture drift and unchanged original indexes for every source. It does not inspect or overwrite the active TUI writer. The latest destination cut is reconciled here; the live destination is still unmodified and landing remains a separate coordination dependency.

### configured-quality-repair | medium | The complete configured aggregate exposed real source and test-support findings

Open final verification. The initial twelve-gate aggregate returned seven failing gates: style, types, imports, unreachable modules, unused symbols, unconsumed exports and dangling docstring targets. Its import scan loaded all4,363 modules and preserved all15 configured contracts; one missing test-helper import was a hard finding. Corrections preserve the configured scopes and zero-target gates. Domain six-export reconciliation is committed44ba3caee7 with299 focused passing cases; the remaining source fixes have their own exact hashes and focused checks. A current filesystem module census is regenerated and the complete aggregate is running against frozen source with before/after hashes. No final configured pass is claimed.

### gnome-reply-lifetime | high | Native reply fields were decoded after the owning D-Bus message was released

Resolved source defect. The retained GNOME login consumer now decodes all seven native fields and checks trailing fields inside bus.call ownership. Existing validation and cleanup remain in their original owners. The regression fixture invalidates its reply when that context exits and detects the captured4d implementation's freed-reply read. Thirteen focused protocol/lifetime cases pass on Windows; this is a portable seam proof, not a GNOME desktop acceptance claim. Actual Linux filesystem/protocol checks are separately owned and their native results remain pending here.

### gnome-resource-placement | low | Disconnected producer setup belonged to deferred product provisioning

Resolved placement within the accepted scope. Exact non-activating resource publication and its tests move to one standalone development packaging utility. The isolated script path uses installed product imports and refuses a nonisolated interpreter before setup. Packaged GNOME resources and the actual production login consumer remain; the storage taxonomy names that real consumer. No console wrapper, forwarding alias, autostart or gate exemption is introduced. Twenty-five focused cases pass with17 actual Linux filesystem cases skipped on Windows, and the final development-script replay passes all10 cases.

### installed-withholding-home | medium | The actual installed continuation exported its first work but did not establish the Home transition

Open diagnosis and native dependency. The final-cut Mac cohort passes14 containment/peer/Keychain cases, one mutually exclusive locked-context detector skips, installed MCP passes its selected test and actual public SDK smoke, and seven terminal-driver regressions pass. The actual CLI seed creates all7 works. The first lifecycle child observes its first real export, then fails to establish public Home refresh; the independent export oracle, local recording and fresh-child reopen are not reached. Finite public refusal/visibility/posture diagnostics are repaired with focused passing tests. The selected Mac host is offline, so that next actual diagnostic and the complete seven-work/two-child proof remain unexecuted. No private exception text, timeout extension or lock-policy bypass is introduced.

### windows-package-and-custody | medium | Artifact proof passes while protected-session admission still lacks its required host context

Scoped artifact verification passes on4d source: all6 configured CMake tests, actual ZIP hash verification and hostile relocation, and application readiness from the actual extracted Unicode-path ZIP. The subsequent shipping-source repairs require a refreshed final artifact before a current-package claim. This runner is elevated and lacks an interactive desktop, so it cannot establish positive protected-storage or installed grant/reconnect acceptance under the strict policy. An existing suitable Windows host is requested; no scheduled task, desktop bridge or provider-policy weakening is used.

### later-tui-53f-reconciliation | low | Defining owners reconcile the immutable later cut while preserving current MCP behavior

The actual merge uses integration checkpoint dd69ed8c349 and committed TUI53f01bc87b against original base a8a7fb7d26. All729 conflicted paths have source resolutions:652 catalogue conflicts preserve31,487 completed translations and4 individually reviewed existing translations;30 assigned product/runtime conflict paths plus the remaining shared/source/vault ownership are recorded separately. Existing historical record restoration preserves delegated acceptance, additive receipts and the committed binding-plan retirement; it authors no new decision or checkbox. Exact original-base binary deltas and resolved tree evidence account for all4858 incoming paths. Generated9 targets/forms retain current valid committed bytes as bootstrap until newer interpreting inputs settle; this is not final reproduction proof.

### current-startup-contracts | high | Automatic merge regressions repaired without weakening authority or schema admission

Three incoming clean merges lost current behavior: invoice models/payload normalization removed the M347 leased-premises family still required by real consumers, and evidence-followup DTOs introduced a custom UTC schema that the closed operation registry correctly refused. The restored current fields, canonical cadastral normalization and plain datetime/UTC validators preserve the intended semantics while retaining direct canonical EU imports. Actual collection now succeeds for339 cases, including272 unique primary operation identities and54 supplementary variants. Three pure completeness/duplicate/installer-environment cases pass;44 surviving product paths pass AST, style, format and type checks. These startup defects are resolved at source/collection scope; fresh behavioral replay remains required after final inputs settle.

### desktop-terminal-cleanup | high | Incoming detached workers and unbounded shutdown replaced by retained bounded settlement

The incoming Desktop preview spawned reader, writer and ConPTY closer threads without retaining handles, waited for its child without a deadline, and dropped Session ownership before checking cleanup. Current source retains each JoinHandle, polls child exit and finished joins under one3-second deadline, retains Session on explicit failure, preserves primary failure through retry and refuses normal window closure until settlement. Source review and pinned Rust formatting pass. The two meaningful worker tests and actual packaged PTY/Desktop execution are pending. Unexpected OS/process destruction is explicitly not certified as joined cleanup. This introduces no runtime manager, persistent service or scheduled task.

### live-destination-preservation | low | Later active writer state captured independently without changing its checkout

The live destination advanced to efb85a8a5b and remains dirty. Immutable snapshot66b785a1418 preserves248 later working paths against that original head. Original index SHA256 is unchanged at61e6120a68ab41d15a102258e02866e73de78c924bcddc3958a67d265f88ebc4. Two capture trees differ only at the registry-health audit, so the preservation is explicitly a time window. Six active source/catalogue lock paths have named transient dispositions and are not transplanted. Native layout/uninstall changes and captured M232 form/static interpretation changes require their own semantic reconciliation before a single final generation pass. The live worktree has not been updated or landed.

### native-stage-ownership | high | Existing installer staging could be erased without an owning unchanged receipt

Resolved source defect. Native preparation preserves every preexisting stage, validates its exact owning receipt, and builds a fresh candidate before reusing only byte-identical input. A missing receipt, modified stage or different candidate refuses with a fresh-build-directory action. It never recursively erases existing staging. Real filesystem regression tests cover unrelated files, modified receipts and changed payloads.

### native-uninstall-identity | high | Path-based deletion could remove a replacement after preflight

Resolved per-file identity and namespace defect. Windows retains no-reparse ancestry and a read/delete handle that denies write/delete sharing, hashes that handle and deletes that exact identity. POSIX retains directory descriptors, claims into its own private no-replace namespace, verifies inode and digest there, and restores a changed claim without replacing newly appeared names. The manifest anchor is removed last; modified/unowned state and directories remain. This does not promise byte compare-and-delete against arbitrary previously opened POSIX writers or an atomic multi-file uninstall. Fresh configured Windows filesystem tests pass39 with2 POSIX-host skips; actual WSL tests pass33 with no skips. Source proof is in .codex/handoffs/tui-all-mcp-native-installation-ownership-repairs.json. Actual shipping installer/Desktop acceptance remains pending.

### latest-tui-product-and-catalogues | low | Captured later intent is reconciled with current public defining owners

All248 captured66 source paths have dispositions against originalbaseefb85 and currentf39. Twelve product paths preserve current IVA public projection helpers while sharing StrictRegistryToken, add typed M360 producer/header facts and source-independent tests, and retain actual profile verification workflows. The physical DR145 page slot is optional; the obsolete missing-page export refusal is superseded by the independently constructed full610-byte export/event oracle and genuine absent/blank/C success plus invalid-enum refusal cases. The family matrix retains272 primary identities and54 supplementary variants. Product126 pure cases and scoped AST/Ruff/format/type checks pass. The186 catalogue application preserves all current message identities and metadata while carrying2395 completed translations; no existing nonempty translations are replaced. Both catalogue batches have zero incoming message-level fuzzy-clear deltas.

### current-integrated-static-review | low | New ownership and producer interactions have no remaining high static finding

Independent bounded review finds no concrete critical/high defect in changed native ownership, M145 physical-slot rules, typed M360 producer facts or finite public Home diagnostics. Unchanged retained Desktop worker sources reuse their prior exact-hash review. This is static evidence. Generated authority/layout closure and the current configured12 gates are running; fresh affected behavior, final installed artifacts/Desktop, offline Mac lifecycle/reopen and safe live-writer landing remain unresolved verification dependencies. Existing pending review status remains PENDING.

### current-invoice-request | high | Automatic merge removed leased-premises request fields still consumed by the current TUI

Resolved in c2a6199fd3. The request restores the three original M347 fields, defaults, defining enum and cadastral length constraints used by unchanged operation and TUI consumers. Four actual DTO/schema/invalid-enum/secure TUI relay cases pass, with scoped Ruff/format/ty/pyrefly/basedpyright passing. No caller or failure expectation was rewritten to hide the missing fields.

### joint-registry-publication | low | Source-pinned companion forms and retained authoring metadata close all generated targets

Resolved in8be18a88ab. The defining generated-form bridge preserves every original M232 pin and adds reviewed M190 source/manifest/form pins. Wrong identity, old form drift and publication failure refuse; joint success requires canonical form regeneration, complete authority validation and final target currentness. M347 optional/repeat metadata is restored at its authored owner without replacing already-current generated records. All20 affected targets are exactlyCURRENT and allnine earlier bootstrap artifacts have individual owner proof. Canonical validity/runtime-load/integrity pass58modelos/160revisions; logical authority1a8dc024bc0cf73719f36174f63faea00914ed74281625fcd512005284bffd6b. M190 final-source positive replay passes274.47s including cleanup with explicit runner --timeout=600; the ordinary300s teardown timeout remains recorded separately.

### final-configured-quality | low | All twelve configured gates pass on frozen source and checked data

Resolved configured verification. The actual owning dev.quality.suite runs all12 configured gates and returns0 from01:34:46 to01:46:04UTC with zero before/after source, checker-metadata or checked-data drift. This suite is intentionally quiet on success. Actual current files are committed in8be18/74d6/c2a; Git commits did not change the checked bytes. The prior9PASS/3FAIL and11PASS/1unavailable changed-source runs remain preserved with their real diagnostics. Later literal-only M145 test-premise repairs need their scoped supplements. Behavioral acceptance, current installed Windows/Desktop, offline Mac withholding/reopen and safe live-writer landing remain pending; review status staysPENDING.

### independent-final66-review | low | Combined authority and ownership boundaries retain their intended behavior

Independent final66 integrated static review found no remaining high or critical defect in the reviewed authority, consumer and native ownership boundaries. CLI/TUI/MCP retain connection-bound admission and frontend permissions; corpus citations retain one authority pin. M347 request facts reach domain validation and current inmueble observations. M145 absence renders the principal blank wire byte while explicit markers retain the declared C constraint. Joint generated repairs keep exact historical pins and require final live validation; failed companion repair discloses the incomplete interval. Retained Desktop bounded workers and native exact-file ownership match reviewed source hashes. Actual installed Mac execution, protected Windows context, complete behavioral/E2E and destination landing remain pending. Static and packaging evidence does not establish those outcomes.

### m145-fixture-premise | medium | Old explicit-space semantic seeds conflict with the retained source-backed optional C indicator

Resolved fixture premise at source; affected behavioral replay pending. The real minimal adapter reproducer returns invalid_value because the captured66 casilla explicitly allows declared C and uses an absent optional value for principal. Official DR145 row2 still requires byte10blank or C. Two test-only preparation files omit the marker instead of submitting literalspace; every610byte/hash/receipt and invalidX/c/CC oracle remains. Scoped Ruff/format/ty pass; production code and authority are unchanged. The in-flight Serial interpreter retains old seeds, so its affected failures and source drift will remain visible. Final M145 owner/family cases replay separately; unchanged family results are reusable only within that stated scope.

### current-operator-and-fixture-owners | medium | Current runtime contract and meaningful invoice summary restored with independent fixture premises

Resolved at source and covering behavior. The defining operator contract retires the stale app.runtime mount already absent from the accepted command graph. A real missing invoice lease summary dropped the supplied premises; canonical locale set-batch adds both placeholders in all four supported languages without changing the caller or assertions. Browser tests now establish the actual controlled-category environment, and the atomic reconciliation test addresses the public PreparedModeloReconciliation.persist owner while retaining actual SQL rollback and grounding assertions. Whole five-owner replay passes46 cases in13.02s, including unchanged refusal-target and leased-premises TUI assertions. Scoped Ruff/format/ty and four YAML/placeholder checks pass. Authority is unchanged. Current installed payload proof must include these real contract and locale changes in the coordinated final rebuild.

### m145-complete-affected-replay | low | Independent DR145 oracle retains exact wire proof using the current typed decimal slot

Resolved. The supplementary independent oracle accepts the defining physical decimal type instead of the retired money label; it still independently fills absent numeric slots and never calls the shared codec. The whole adapter14, primary5, supplementary5 and completeness/duplicate2 replay passes all26 in103.29s. Its actual passed-node union covers all13 original serial failures; the other424 passing serial cases remain preserved separately, giving scoped coverage of all437 selected serial cases. Raw serial exit1 remains visible. Three unrelated CLI fixture paths changed during replay, so global zero-drift is explicitly not claimed; M145 owners, authority and physical export oracles were unchanged. Later runtime admission changes have a separate owning replay and this receipt does not establish combined native or destination acceptance.

### installed-cli-bootstrap-adapter | low | Native acceptance uses the existing console bootstrap through every fresh CLI child

Resolved acceptance runner wiring. The optional immutable cli_argument_prefix precedes CLI options and is preserved by both IVA reopen adapters and sanitized receipts. The actual console entry is cadrumo.entrypoints.cli.bootstrap:main via the existing interpreter -c invocation; the package has no __main__, and the earlier -m attempt is recorded as a runner error. Profile creation and authenticated secrets remain stdin-only with the existing custom-stdin conflict guard. Fifteen scoped adapter tests pass in1.76s, preserving incomplete-verification refusal and both fresh adapter boundaries; Ruff/format/ty pass on all four paths. These mocked adapter tests do not prove product calculation, export or native custody. The dev acceptance helpers are outside actual native action and wheel membership; installed native journey replay remains required.

### replacement-binding-admission | high | Immediate successor login now retires the predecessor through canonical containment

Resolved production race. A committed successor binding previously met the cached predecessor until the 0.5s polling cycle, refusing an immediate legitimate fresh login. Admission now releases the connection map guard, attempts the canonical bounded retirement, removes only a proved contained incarnation and reobserves the current binding. A nonblocking retirement fence prevents a competing caller treating denied authority as containment; failed cleanup retains worker ownership for retry. Enrollment removal selects the exact host and takes offers atomically before closing outside its guard, preserving successor offers and leases. Three deterministic actual-Windows-worker tests pass, including held commit guards, concurrent and failed retirement, callback map borrowing and stale-cleanup successor preservation. Ten complete affected runtime/recovery modules pass62 with no failure or skip in926.14s; the plain public forgotten-passphrase reset passes36.58s without the diagnostic observer. Four production and one test path pass scoped Ruff/format/ty. Five unrelated CLI fixture/test paths and Git HEAD changed during the run; relevant tested owners and authority did not, so no full-tree zero-drift is claimed. Native Mac containment and the changed compiled Windows interpreter remain separate required proof.

### native-kdf-environment-producer | high | Packaged child projection contradicted its neutral pre-secret attestation

Demonstrated installed producer defect, corrected at source; compiled/installed verification pending. The genuine M303 first profile command reached the packaged KDF child before any password request, but native application environment projection removed four declared Python keys and added six application keys. Strict readiness correctly refused. The Windows host now preserves supplied neutral environment only for the complete fixed seven-argument KDF invocation with two distinct canonical positive pointer-sized decimal handles. Ordinary and near-match invocations retain application projection. Context derivation, DLL lookup, isolated CPython, package startup hash checks and the parent Job/cwd/environment/frame pre-secret attestation are unchanged. The owning package verifier adds an actual no-request ready/join/neutral-cleanup proof and a real valid-parser extra-option refusal/join proof. Scoped Ruff/format/ty, embedded-probe compilation and diff checks pass. Independent baseline source review and root integrated review identify no remaining high/critical source finding. These static checks do not establish compiled execution, protected storage or financial E2E; the sole coordinated source-matching artifact refresh must execute both probes and the actual journey.

### typed-revision-selection-and-mismatch | medium | Validated amendment records retain their aggregate context and finite public mismatch facts

Resolved production defects. The internal selection holder now retains an already repository/aggregate-validated CalculationRevision in a frozen slots dataclass rather than revalidating it without the aggregate. No public, persisted or candidate schema changed. The existing mismatch refusal now declares finite axis, requested/law revision and captured modelo/year/period context for the bounded public detail boundary; raw args and redaction policy are unchanged. Both complete selector/D1 owner modules pass29 with stable three source hashes; actual amendment11 and all four scope/privacy CLI cases pass in the separate combined17pass/1unrelated test-premise failure run, retained with exit1. Scoped Ruff/format/ty pass. Fresh native artifact inclusion and combined verification remain separate.

### recorded-modelo-scope-detail | medium | Work creation and readiness retain declared public diagnostic context through settlement

Resolved production omission. Work-create and readiness alone opt in to the existing public executor error-detail boundary; all other read definitions retain defaultFalse. Request/result/refusal serializers, registered capability/access guards and raw-private error policy remain unchanged. Two new cases exercise the real definitions/executors with a fault injected at the defining ports factory, then actual encrypted journal settlement, guarded detail projection and typed serialization. The whole seven-case owner passes, including retained private/redaction controls. The two affected positive operation matrix cases pass; all four actual CLI scope/privacy cases pass after the companion typed-context repair. Scoped Ruff/format/ty pass. These portable injected fault cases do not establish native/provider or installed E2E acceptance.

### observable-portable-command-probes | medium | Capability detectors reach real handlers through genuine admitted test sessions

Resolved fixture premises. Five test-only paths establish registered credential profiles, genuine password cryptography and runtime admission through explicit synthetic OS transport/custody ports and joined workers. The API fixture performs canonical request/approval/delivery/possession to COMPLETE and uses its opaque key; it never fabricates HUMAN elevation or API authority. Real expired ENROLL/own-key ROTATE operands reach the unchanged administration validator and observed False without lending governed-fact scope. Typed UUID/digest and required year/certificate premises are supplied. NIF-IVA retains its deliberate product refusal: the probe partition records its exact CLI code/effectNONE/no contact and the owning supervisor proves refusal before provider/browser work. Complete two-module replay passes142 with no failure/skip, including both deliberate undeclared detector teeth and offline seal. Ruff/format/ty pass on all five frozen files. One documented startup CRLF-to-LF drift has byte-normalized and position-inclusive AST equality; no raw zero-drift or physical native custody claim is made.

### modelo-cli-owned-premises | medium | Real admitted scenarios retain financial and safe refusal oracles

Resolved fixture premises on13 test-only paths. The shared seeder registers genuine password custody and retains its exact encrypted setup oracle separately from joined human frontend admission. Public calls keep the existing no-seed path; native helper callers retain their actual native path. Private Modelo, M303 secure evidence, amendment, period and invoice direction scenarios now invoke the seeded registered runtime. Unknown selections assert the deliberate safe operation-denied refusal without exposing candidate IDs. Reciprocal capital-goods cases assert the independent registered catalogue message and declared identity context. All four locale action assertions retain the defining current wording. The controlled note-bearing calculation remains BORRADOR with no copied verification grant; genuine verify returns its note-specific refusal, default/explicit export and file retain their earlier state guards, no artifact or filed pointer appears, and clearing/recalculation/verification/export succeeds. All16 owned paths including the separately committed3 public-detail paths pass scoped Ruff/format/ty and are frozen. Canonical latest per-node union is133PASS/0FAIL/0SKIP with qualified reuse across recorded runs, rather than a relabeled whole-suite pass. Original failed receipts and call-order diagnoses remain preserved. Six owning import inventories regenerate/check with zero byte changes; no checker policy or exemptions change. Native installed/provider/desktop/destination proof remains separate.

### portable-kdf-defining-owner | high | Cross-package private fixture imports removed without changing the behavior under test

Resolved source ownership defect. The first frozen configured aggregate passed11 gates and failed import authority with17 private custody module/symbol accesses in the CLI fixture. The joined KDF worker and public test context manager now live as defining implementations in the narrow custody test package; all three consumers import that public manager directly, and no CLI facade, forwarding alias, suppression or checker exemption remains. Parser/crypto/frame/join/context-manager bodies have identical AST to the original5737 fixture. Four files pass scoped Ruff/format/ty and eight actual human/API/AEAT/guard/detector/offline-seal cases pass47.49s. The supported configured UV import gate passes authoritatively with15/15 contracts,4368/4368 production modules loaded and zero hard findings; source snapshots match. The earlier plain-Python retry is retained as unavailable because its tool PATH omitted lint-imports, despite zero hard findings. Original142-case proof remains qualified by behavior-preserving ownership relocation; current native action fingerprint refresh is still required because its declared input scope includes tests, although shipping bytes are unchanged. Final whole configured aggregate and native/provider/landing obligations remain separate.

### later-m347-physical-oracle | low | Current leased-premises export retains independent situation and reference byte assertions

Incorporated the unique three-line oracle from fresh preserved live TUI snapshot78d675 relative to66b785. The current public/pinned schema helper and historical filing grade remain intact. The independent source-pinned M347 fields f011/f012 declare one-based offsets115/116 and lengths1/25; the existing fixture independently declares situation1 and literal cadastral reference. The test now checks those exact output spans in its I record. The whole owner passes3 in2.51s with no failure/skip and scoped Ruff/format/ty passes; source byte hashes remain stable. No shipping model, DTO, compiler, authority or data changes are imported. All119 later source deltas are accounted by the external review: one adapted unique oracle, three exact, three semantic, and one policy/factoring already-present cases, and111 independent ongoing cases preserved without blind import. Final metadata records the incorporated oracle separately; the active nested lease migration and live destination handoff remain separately coordinated.

## Recommendations

Finish the concrete conformance families, diagnose and complete the installed withholding continuation, corroborate generated registry reproduction, rerun the configured checks against frozen inputs, and obtain the final integrated code review. Preserve failed and unavailable runs beside passing evidence and retain their actual causes. Finish per-path integration commit mappings and coherent provenance-bearing checkpoints. Close only Steps whose required proof passes. Coordinate the final destination update if its writer remains active; the exact landing operation and dependency must stay explicit.

Current review status is PENDING. Static review has no unresolved critical or high defect; combined verification and landing remain open.


## Baseline checkpoint after user priority change

The user explicitly directed committing the complete reconciled MCP baseline before remaining verification. Product source and coupled public CLI consumers are committed in e977df5ac5; tooling, documentation, canonical configuration and historical records in68258c3539; native packaging and the independent application host in fb802220bb. Earlier discovery4e7392a2ee and containment01480b047a checkpoints remain separate. S03/S04/S05 remain open until their required proof and landing conditions are satisfied.

The interrupted affected cohort completed527 cases:466passed,61failed,41of568uncompleted. Fifty-seven failures used the previously loaded incomplete scenario matrix; its replacement scenarios exist. The remaining failures include completeness and browser/native fixture prerequisites plus one custody registration failure requiring replay. No complete suite pass is claimed. Verification replay and final combined gates are deferred until after this concrete baseline, as requested.

The installed CLI failure was a demonstrated production defect: generic materialization created the derived runtime namespace0755. The correction creates a new application-owned namespace0700 before its descendants while preserving existing and explicit insecure namespaces for refusal. Portable checks passed22tests with one host skip; fresh-wheel Darwin checks passed all3cases in1.06s, including real endpoint admission and both insecure namespace refusals. The wheel matched all3218shipping Python modules.

Canonical registry gates passed58modelos,160revisions and1502legal references. A fresh M3902022render comparison reproduced all14committed files with no semantic, source-pin or provenance drift. The published logical authority remains5375497a63086b77cb673bf468f370ea944af86f6892190132b5e67bc2bc3308.

Native installed withholding seeding now succeeds. Its lifecycle child failed before proving completion; the safe failure-receipt repair retains driver stage and sanitized public screen/widget identities, with17focusedtests passing. The full fresh native continuation is being replayed; no successful lifecycle or reopen is claimed. Native containment and unlocked Keychain passing evidence above remain valid for their unchanged owners.

The immutable later destination cut60c063bba1fc3d53f7d0c2522405a81966a6a0a8 will be reconciled only in the isolated branch. The active live checkout has4888observed status paths and cannot be overwritten. Review remains PENDING for combined verification and landing.

## Verification resumed after baseline delivery

The active user goal now requires isolated-branch E2E, landing after green on feature/tui, and E2E in the actual destination checkout. The earlier baseline-first deferral is retained above as history. Current verification, review and safe landing are active; the live writer remains untouched and the integration is not landed.
