---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `live-iva-compensation-wallet` Code Review

## WALLET-001 | HIGH | False-zero wallet observations can be persisted from a no-result shell

`parse_iva_compensation_wallet_html` accepts an executed wallet shell with no table and no explicit AEAT `0,00` aggregate as `total_pending=0` when `allow_empty_wallet_shell=True`. That can persist and reconcile as a non-blocking `wallet_only` authority. The parser must require an explicit AEAT zero aggregate or a specific no-balance marker before storing zero evidence.

## WALLET-002 | HIGH | Representation gate submit is not bounded by inspected form evidence

The own-name representation gate clicks the configured own-profile selector and submits the configured form button, but it does not inspect the representation form action, method, own-name selected state, or representative controls before submission. A changed AEAT gate shape could turn the action into a represented-taxpayer/operator-choice submission. The driver must validate the form boundary and selected own-name payload before submit.

## WALLET-003 | HIGH | Modelo lifecycle gates do not require matching wallet authority

Modelo 303 verification, filing, and export only reject persisted blocked wallet decisions. A revision carrying prior-compensation casilla 110 can still proceed if the wallet decision is missing, stale, mismatched, or deleted after calculation. Lifecycle gates must require a persisted non-blocking decision matching taxpayer, period, and revision compensation value.

## WALLET-004 | HIGH | Reconciliation persistence can drift across repository instances

`reconcile_modelo_303_iva_compensation` accepts an injected observation repository but persists and reloads decisions through a default `IvaWalletDecisionRepository`. Tests and live capture can compare local recurrence from one secure store while saving authority into another. The orchestration must accept and thread an explicit decision repository or shared secure-object repository.

## WALLET-005 | MEDIUM | Diagnostic dumps write raw live pages outside secure storage

When enabled, the wallet diagnostic dump writes full HTML, frames, screenshots, and summaries to an operator-provided path. These files can contain live taxpayer amounts and identity-bearing evidence. Diagnostic capture must be removed, redacted, or routed through encrypted secure-object storage with an explicit inventory classification.

## WALLET-006 | MEDIUM | Wallet result target period is not verified from rendered page evidence

The parser stores the caller-provided target year and period without validating AEAT's rendered `Ejercicio` and `Período` labels. A stale/default/wrong-period result can be persisted as evidence for the requested target. The parser must require exact rendered target labels when they are present on the wallet result page.

## WALLET-007 | MEDIUM | Wallet source provenance is dropped before revision/export surfaces

The source resolver builds decision provenance, but calculation revision observations later receive generic registry provenance. The wallet decision key/fingerprint and authority source kind should remain visible in revision/export provenance.

## WALLET-008 | MEDIUM | Live-success `wallet_only` path lacks downstream lifecycle coverage

The observed live success path produced a non-blocking `wallet_only` decision. Downstream tests cover match, blocked divergence, filed-history-only, and override, but not `wallet_only` through calculation, verification, export, and file gates.

2026-06-03 follow-up: non-private real-engine coverage now exercises wallet-only evidence through reconciliation, Modelo 303 calculation, and lifecycle authority matching. Export or file happy-path coverage remains open.

2026-06-03 S84 follow-up: non-private real-engine coverage now also exercises `wallet_lower`, `wallet_stale`, and missing wallet/local recurrence decisions through the Modelo 303 calculation boundary.

2026-06-03 S85 follow-up: full non-private Modelo 303 `wallet_only` export coverage now runs the production create, calculate, verify, and `export_modelo_revision` path against the registry-backed fichero layout. The remaining downstream gap is the separate local-file workflow harness work tracked in the plan.

## WALLET-009 | LOW | Wallet action labels are duplicated outside centralized constants

Wallet browser action labels are defined locally in the Sede adapter while the same strings also live in the centralized external constants allow-list. The code should consume named centralized settings/schema values directly.

## WALLET-010 | LOW | Backend test contains hand-implemented arithmetic

`test_iva_wallet_capture_backend` computes an expected available-end amount from local arithmetic. The assertion should use seeded persisted fields or production repository output instead of test-local business arithmetic.

## WALLET-011 | LOW | Fixed stale blocked-only lifecycle helpers after strict matcher replacement

The review-closeout pass found unused private helpers that preserved the old "blocked decision only" lifecycle path after Modelo 303 verification, export, and file moved to the stricter persisted-decision-and-revision-amount matcher. The stale helpers were removed so there is a single lifecycle authority check for IVA wallet decisions.

## WALLET-012 | MEDIUM | RESOLVED | Modelo 303 wallet-only export happy path needed real registry-backed coverage

The earlier blocker statement was stale after the registry consolidation: Modelo 303 now has fichero-BOE export-layout TOML under the registry tree. S85 adds non-private happy-path coverage that creates a Modelo 303 work unit, calculates with a persisted `wallet_only` AEAT wallet authority decision, marks the revision verified-complete, exports through `export_modelo_revision`, and verifies redacted wallet provenance in the service result and bucket event.

The test also records two real preconditions that the export path enforces: the profile must carry a valid Spanish tax identifier and `identity.surnames`, and the synthetic filing must include the prorrata volume inputs needed for the registry formula trace.

## WALLET-013 | MEDIUM | Wallet-only local file happy path needs a non-fake workflow harness

The internal `file_modelo_revision` path is local-only, but its happy path still runs the workflow gate and needs an auth provider. Existing file-flow tests use a test provider seam; adding another fake or stub conflicts with the current test mandate, while using a live provider would risk external AEAT contact. The remaining wallet-only file happy-path step should first define an accepted real-behavior local workflow harness that proves no AEAT submission occurs.

2026-06-04 S83 follow-up: resolved. The new local lifecycle regression uses the real Cl@ve provider selection path with synthetic local settings and only exercises provider `describe()` through the read-only `SubmissionEngine.preflight()` boundary. It creates a non-private `wallet_only` Modelo 303 decision, calculates the revision with the production engine, marks it verified-complete, and calls `file_modelo_revision()` without an injected workflow engine or live AEAT session. The test also proved and fixed a critical period-token mismatch: Modelo 303 work units now target the deadline-engine `YYYY-nT` period shape, and the central period parser accepts that shape for downstream registry resolution.

## WALLET-017 | MEDIUM | LIVE-OBSERVED | 2026-06-04 read-only remote-state capture succeeded via persisted Clave session reuse

The 2026-06-04 live read-only `capture-remote-state` run for 2022-2026 / target 2026 2T completed with `auth_status=succeeded`, `auth_outcome=authenticated`, `auth_provider_kind=clave_movil`, and `auth_reused_persisted_session=True`. Both filed-history and wallet/cartera surfaces succeeded, and the backend reload reported 12 IVA compensation history rows, 8 carry-forward lots, 2 authority decisions, 11 wallet observations, and 23 acquisition manifests. The visible 2026 1T and 2T authority decisions select `aeat_wallet`, carry `wallet_only` divergence, and are neither blocked nor stale.

Operator-observed fresh phone approval is intentionally not claimed for this specific successful run because the CLI reported persisted-session reuse. The immediately preceding fresh-auth attempts were recorded honestly as one operator-timeout failure and one interrupted/timed-out command with the process tree explicitly cleaned up. The operator-confirmation question remains open: whether any new Clave prompt was actually seen during the successful persisted-session run.

## WALLET-057 | REVIEW-PASSED | W11.P25.S95 live-test env var separated from operator live-read gate

Review scope covered the live-read gate split in `AeatAccessGate`, the auth-login translation path, stale production wording in live CLI/auth modules, and focused tests for pytest versus operator contexts.

No HIGH or CRITICAL issue was found in the local review. The permanent live-write gate remains unchanged in `require_live_write`. Operator live reads no longer fail solely because `AEAT_LIVE_TESTS_ENABLED` is unset or set to a non-literal value outside pytest; they continue into the existing auth/profile/read-only acquisition path. Pytest execution still refuses live reads unless the setting is literal `1`, and the pre-existing pytest marker hook still deselects/skips `live_read` tests by default.

A focused `vaultspec-code-reviewer` check returned no finding on the centralization question: `login_operator_auth` now calls `AeatAccessGate.require_live_read(pytest_current_test=...)` and translates `AeatLiveReadNotEnabledError`, so the literal env-var decision remains owned by `AeatAccessGate`.

Verification completed:

- `uv run ruff check` passed for the touched gate, auth, live CLI, auth adapter, and focused test files.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py -q` completed with 30 passed.
- `uv run pytest` for the four legacy CLI live-gate ordering tests in `test_registry_cli.py` completed with 4 passed, proving pytest-context invocations still refuse before local writes.
- `uv run pytest src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/application/live/test_iva_wallet_live.py -q` completed with 7 passed and 1 deselected.

Residual risk: the broader `AEAT_LIVE_TESTS_ENABLED` inventory and static-guard work remains open under `W11.P25.S94`, `W11.P25.S96`, and `W11.P25.S97`. The earlier `vaultspec-rag search` local-store lock/timeout ambiguity is closed under `W10.P24.S98` as typed tooling diagnostics; upstream service stability remains an external tooling risk, not a silent AEAT discovery claim.

## WALLET-018 | HIGH | LIVE-RESOLVED | Fresh Clave auth and read-only IVA remote-state capture verified

The 2026-06-04 live-auth regression was re-tested through an isolated auth-first sequence. The persisted Clave session was cleared, `config auth login --provider clave_movil --fresh --reset-lock` was run, and the operator reported seeing and approving the phone request. The CLI returned `authenticated=True`, `fresh=True`, and `reused_persisted_session=False`, proving the fresh Clave phone-auth surface was functional for this run.

Immediately after that fresh login, the read-only `capture-remote-state` run for 2022-2026 / target 2026 2T completed with `auth_status=succeeded`, `auth_outcome=authenticated`, `auth_provider_kind=clave_movil`, and `auth_reused_persisted_session=True`. That reuse is expected because it consumed the fresh session created in the preceding login step. Both filed-history and wallet/cartera surfaces succeeded. Backend reload reported 12 IVA compensation history rows, 8 carry-forward lots, 2 authority decisions, 12 wallet observations, and 25 acquisition manifests. The visible 2026 1T and 2T authority decisions select `aeat_wallet`, carry `wallet_only` divergence, and are neither blocked nor stale.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed. Process checks after the run showed no remaining `config auth login` or `capture-remote-state` command process.

## WALLET-014 | LOW | RESOLVED | S85 test committed a full valid-looking synthetic NIF literal

The S85 review found that the new happy-path export test initially used a full checksum-valid Spanish tax-id string literal. It was synthetic, but the privacy posture for this surface is stronger if tests derive valid identifiers without committing the complete token. The test now derives the valid NIF with the shared checksum helper at runtime and keeps the result/event redaction assertions unchanged.

## WALLET-015 | HIGH | RESOLVED | Own-name dispatcher guard needed represented-text refusal

The S86 review found that accepting AEAT's `DialogoRepresentacion` own-name dispatcher while only rejecting the representative radio was too weak: a drifted page could carry prefilled representative text fields and still pass the radio-only guard. The wallet reader now fails closed when any text-like input in the representation form has a non-empty value, and the diagnostic context still reports only structural input metadata, not the field values. Focused tests cover the accepted own-name dispatcher, the rejected representative radio, and the rejected represented-text case. A post-review 2026-only live read-only capture still succeeded for filed-history and wallet/cartera.

## WALLET-016 | HIGH | RESOLVED | Backend remote-state reload depended on CLI bucket-session bootstrap

After live wallet success, direct backend verification exposed that `load_iva_remote_state()` could fail outside the CLI root callback because no active bucket session was open. That made the backend reload surface weaker than the live capture surface, even though both operate on the same active-profile secure storage. S87 routes `list_iva_compensation_history()` and `load_iva_remote_state()` through an application storage-span helper that opens the active profile session only when no session is already active. The regression test uses real profile registration, closes the session, and then proves direct backend reload works without CLI bootstrap. The current active-profile reload was also verified with redacted aggregate output only.

2026-06-04 review follow-up: the first S87 patch still allowed the no-active-profile case to fall through to default/root storage. That is now fixed: remote IVA reload raises a storage readiness error when no active profile exists, and a focused regression test locks that fail-closed behavior.

## WALLET-019 | HIGH | RESOLVED | Modelo 130 workflow-period mapping regressed after the Modelo 303 quarterly fix

The S77 focused gate exposed a production period-mapping regression: the shared Modelo workflow period resolver mapped every raw quarterly work-unit token to the Modelo 303 deadline-window spelling. That preserved the 303 `YYYY-nT` fix but broke Modelo 130 lifecycle filing gates, whose registry deadline windows use `YYYYQn`. The failure was real: the workflow gate reached `NO_PENDING_OBLIGATION` or a draft/input mismatch before filing preflight, so internal file-flow state transitions did not exercise the intended production path.

The resolver now consults the modelo registry's declared deadline windows and returns the exact matching period token for the work unit's `(modelo, filing_year, registry_period)`. Regression coverage proves Modelo 130 resolves to `YYYYQn` while Modelo 303 resolves to `YYYY-nT`, and the file-flow harness now consumes the production resolver instead of reimplementing period spelling locally.

## WALLET-020 | LOW | REVIEW-PASSED | Final W09.P22 closeout review found no remaining live-wallet blockers

The final closeout review inspected the live-wallet/parser/backend/modelo lifecycle diff after S82, S83, S77, and S78. No new critical or high issues were found. Current verification evidence covers read-only live AEAT capture, backend reload, wallet parser and constants, Modelo 303 wallet decision binding, lifecycle authority matching, export/file local paths, Modelo 130 period compatibility, and Modelo 714 Phase-A registry drift. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-021 | MEDIUM | RESOLVED | Clave own-name representation action label still had a local source of truth

The W06.P16 closeout found that the Clave auth driver still carried a local hardcoded own-name representation browser-action label, while the wallet driver and settings schema already used the TOML-backed Pre303 constant. That weakened the central settings mandate and made future action-label drift harder to detect.

The auth driver now reads the own-name representation action label from external constants before passing it through the remote-state guard. Guard coverage proves the configured own-name action is allowed, an unclassified represented-taxpayer representation action is rejected, and the universal browser-action guard rejects filing, signing, payment, and confirmation actions. The remote-state guard now treats bare Spanish confirmation labels as write-class tokens.

## WALLET-022 | MEDIUM | RESOLVED | Multiyear filed-history parser coverage lacked a non-private end-to-end chain

The W06.P15 closeout found that the live capture evidence and the existing unit tests covered separate pieces of the filed-history path, but did not yet provide a single non-private regression starting at a Modelo 303 submitted-file payload and ending at profile-local IVA remote-state reload.

The new regression builds sanitized Modelo 303 submitted-file page records for 2025 4T, 2026 1T, and 2026 2T, parses them through the Sede submitted-file parser, persists them through the production IVA compensation history path, and reloads remote IVA state through the active profile storage backend. Assertions cover period keys, generated amounts, available-end amount, two remaining carry-forward lots, and zero unallocated application without using live taxpayer history as a fixture.

## WALLET-023 | LOW | RESOLVED | Multiyear filed-history helper briefly hardcoded a registry snapshot id

The W06.P15 code-review pass found that the new non-private filed-history helper supplied a local `registry_snapshot_id` string. The observation model does not need that field for the tested parser-to-history path, and keeping it local would create an unnecessary source-of-truth literal in the test.

The helper now lets the production snapshot lookup and parser path provide the registry context. Focused parser-to-history coverage and the broader live-application acquisition pair both pass after the cleanup.

## WALLET-024 | HIGH | RESOLVED | Standalone live IVA capture paths could rely on sessionless storage

The S60 storage-drift audit found that the combined `capture_iva_remote_state` path opened profile-bound secure storage, but the standalone IVA wallet and IVA filed-history capture entrypoints did not require the same storage span before auth and persistence. That left a weaker backend route where live evidence could depend on ambient/sessionless storage state instead of the active profile boundary.

Standalone `capture_iva_compensation_history`, standalone `capture_iva_compensation_wallet`, and combined `capture_iva_remote_state` now all enter the active profile storage span before live auth or persistence. No-active-profile regression tests prove all three fail closed before AEAT contact, and the existing wallet backend tests still prove injected repositories keep reconciliation decisions profile-bound.

## WALLET-025 | LOW | RESOLVED | S60 plan row carried stray inline-code markers

The S60 code-review pass found a documentation-only issue in the plan row: normal prose about no-active-profile regressions was accidentally wrapped with inline-code backticks. The row now keeps only real source-path references in inline-code formatting.

## WALLET-026 | HIGH | RESOLVED | Live IVA acquisition failure contexts could persist sensitive identity/support strings

The S63 privacy audit found that live IVA acquisition reports already redacted URLs and auth diagnostic ids, but generic surface failure-context strings could still be carried into persisted acquisition manifests. In particular, a private DNI/NIE, support-number, profile id, secure-object key, or other sensitive token nested under a future error context could survive as plaintext if the key was not URL-shaped.

The acquisition redaction boundary now applies the diagnostic redaction rules to every persisted context string, hashes sensitive-key values to stable evidence refs, and hashes string elements inside generic context sequences. Regression coverage builds a production `SedeNavigationError`, persists the resulting acquisition manifest through profile-local secure SQL, reloads remote IVA state, and proves the raw non-private canaries do not appear in the report JSON, manifest JSON, remote-state JSON, or database bytes. Existing wallet diagnostic coverage continues to prove DOM drift dumps contain structural metadata only, not raw HTML, screenshots, input values, or wallet amounts.

## WALLET-027 | HIGH | RESOLVED | Sensitive parent context mappings needed subtree hashing

The S63 code-review pass found that the first privacy hardening patch hashed direct sensitive-key strings and generic sequence strings, but a mapping under a sensitive parent key could still preserve a plain nested string if the nested key was innocuous, for example `credentials.raw`. The sensitive-key classifier also needed to catch pluralized key parts such as `credentials`.

Sensitive parent mappings now recursively hash their string leaves, and the classifier accepts plural sensitive key parts. The persisted-manifest privacy regression includes a nested `credentials.raw` support-number canary and the broader acquisition/parser/wallet gate still passes.

## WALLET-028 | MEDIUM | RESOLVED | Persisted divergence coverage did not prove all authority sources survive separately

The S64 audit found that domain reconciliation tests covered the divergence ladder, and storage tests covered simple persisted wallet decisions, but there was no single secure-storage roundtrip proving a persisted override decision keeps AEAT wallet, local recurrence, filed-history observation, and taxpayer override sources separate with their distinct amounts.

The repository roundtrip suite now persists a non-private override decision carrying all four authority-source kinds, reloads latest/history/list views, and asserts selected, wallet, local, override, and per-source amounts are preserved without merging. The test also checks encrypted SQL bytes do not contain the synthetic taxpayer id or override evidence locator.

## WALLET-029 | LOW | REVIEW-PASSED | S64 persistence source-separation review found no new blockers

The S64 focused review inspected the new secure-storage roundtrip coverage against the existing reconciliation ladder tests. No critical or high issue was found. The new test exercises the production `IvaWalletDecisionRepository`, avoids mirrored reconciliation arithmetic, and verifies source-kind and amount preservation through latest, history, and list reload paths.

## WALLET-030 | LOW | REVIEW-PASSED | S65 readiness row is satisfied by current localized verification/export gates

The S65 audit found the previously open workflow-readiness wording gap is now covered by current Modelo readiness tests. Focused gates prove localized IVA wallet blocking messages and next actions, verification refusal for filed-history-only authority, export refusal before file emission, real-engine blocking for wallet-lower, wallet-stale, and missing evidence, and explicit taxpayer override unblocking. No new code change was required for S65.

## WALLET-031 | LOW | RESOLVED | S66 needed explicit first-period-zero engine and lifecycle coverage

The S66 coverage audit found that the direct reconciliation suite already covered the closed IVA wallet divergence vocabulary, including `first_period_zero`, and the Modelo 303 integration suite already covered wallet-only, filed-history-only, override, wallet-higher, wallet-lower, wallet-stale, and missing states through production code. The remaining gap was an explicit orchestration-to-engine-to-lifecycle assertion for a persisted non-blocking `first_period_zero` decision.

The new regression drives `reconcile_modelo_303_iva_compensation()` with no wallet, no prior recurrence, and caller-asserted first-period treatment, then feeds the resulting persisted decision into `calculate_modelo_revision()` and `_require_persisted_iva_compensation_decision_matches_revision()`. It proves the wallet binding override and casilla 110 are surfaced as zero, no compensation is applied, and the lifecycle authority gate accepts the zero decision. The broader gate covers direct reconciliation, Modelo 303 integration, export refusals, and localized readiness helpers without private taxpayer fixtures.

## WALLET-032 | LOW | REVIEW-PASSED | S66 post-implementation review found no remaining blockers

The S66 focused review inspected the new first-period-zero integration test, plan row, step record, and audit entry against calculation-grounding, non-tautological-test, and live-write safety rules. The review narrowed the new test away from asserting final result arithmetic and kept the oracle on wallet decision consumption, casilla 110 zero binding, zero compensation application, and lifecycle authority acceptance. Focused and broader S66 gates plus ruff pass after the review fix. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-033 | MEDIUM | RESOLVED | S67 lacked a filed Modelo 390 annual compensation evidence boundary

The S67 audit found that production Modelo 303 period states already reconstruct generated compensation, applied compensation, remaining lots, and four-year expiry review, and registry-backed Modelo 390 continuity tests already reconcile annual totals against four Modelo 303 quarters. The missing boundary was filed Modelo 390 annual compensation evidence itself: casilla 97 and casilla 662 were declared in the registry but had no typed application summary that could cross-check the 303 carry-forward projection.

The new `IvaCompensationAnnualSummary` extractor accepts filed Modelo 390 observations and maps casilla 97 to final-period compensation, casilla 662 to exercise-generated compensation not included in 97, and their sum to the annual pending amount. The new cross-check compares that annual summary to the production Modelo 303 carry-forward report without merging 390 into period history. It keeps prior-year carry-forward lots out of the exercise-specific 97/662 comparison while preserving their expiry-review states for operator review, and flags per-casilla 97 or 662 drift. Matching, divergent, active-prior-year review, and expired-prior-year review non-private tests now cover the happy path and review paths. The translated non-390 input error key is enrolled through the locale CLI for `en`, `es`, `ca`, and `hu`.

## WALLET-034 | MEDIUM | RESOLVED | Full Modelo 390 snapshot merge/provenance remains incomplete for mixed observation sources

The S67 post-implementation review attempted to run the full Modelo 390 binding resolver with ordinary calculation observations and secure IVA-history observations for the same Modelo 303 periods. The resolver currently gathers one observation per `(modelo, year, period)`: if a calculation observation exists it shadows the secure IVA-history projection, so compensation casillas from secure IVA history are not merged into the full 390 snapshot. Narrow compensation-binding coverage passes, and the separate full Modelo 390 continuity test passes with calculation observations only, but the mixed-source full-snapshot path still needs an explicit merge/provenance design before S68 can close.

This is not a live AEAT blocker and no AEAT write path was executed. It is a repository-backed calculation-history gap: downstream code needs to preserve which source supplied each compensation casilla when both ordinary calculation history and secure IVA-history evidence exist for the same period.

The S68 implementation resolves this by merging same-period ordinary calculation observations and secure IVA-history projections before invoking the previous-filing resolver. The merged observation preserves per-casilla source kinds, so Modelo 390 ordinary annual total bindings continue to report `app_filing` while compensation bindings report `aeat_sede_iva_compensation_history`. Repository-backed regression coverage now resolves the full Modelo 390 snapshot from both repositories for the same four Modelo 303 periods without live taxpayer fixtures or test-side IVA arithmetic.

## WALLET-035 | LOW | REVIEW-PASSED | S67 annual-summary implementation has no remaining S67 blocker

The S67 review inspected the annual summary model, Modelo 390 extractor, cross-check logic, Modelo 390 97 binding correction, secure-history generated-compensation projection, tests, locale enrollment, plan row, and execution record. No critical or high issues remain in the S67 slice. The mixed-source full-snapshot gap was tracked separately under S68 because it required repository/provenance design beyond the annual-summary boundary, and WALLET-034 now records that S68 resolution. Focused S67 tests, the full IVA compensation history plus Modelo 390 continuity gate, ruff, privacy/URL scan, and locale audit pass.

## WALLET-036 | LOW | REVIEW-PASSED | S68 mixed-source repository-backed resolver review found no remaining blocker

The S68 review inspected the mixed-source merge path in the previous-filing prefill resolver, the secure IVA-history generated-compensation projection, the Modelo 390 casilla 97 binding, the repository-backed full-snapshot regression, the three-year filed-history repository regression, and the touched Modelo 390 registry tests. No critical or high issue was found. The focused mixed-source test, focused three-year repository test, the broader IVA compensation history plus Modelo 390 continuity gate, ruff, privacy/URL scan, test-shortcut scan, and locale audit pass. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.

## WALLET-037 | MEDIUM | OPEN | Standing live read-only cross-year evidence remains under W06.P15.S56

S68 is complete for repository-backed non-private calculation-history coverage. The remaining live proof gap is tracked by the standing live-verification path W06.P15.S56: a fresh operator-observed read-only live AEAT run must verify cross-year history acquisition without sending, filing, confirming, paying, or modifying any AEAT state.

2026-06-04 retry status: failed, not evidence success. The first `capture-remote-state` attempt did not contact AEAT because the live gate requires `AEAT_LIVE_TESTS_ENABLED` to equal the exact literal `1` and the current environment value was `true`. A process-local retry with `AEAT_LIVE_TESTS_ENABLED=1` reached Cl@ve preflight with active profile ready, NIE identity present, support number present, non-QR Cl@ve, and a 120-second auth timeout, then failed as `operator_timeout`; both filed-history and wallet surfaces failed because authentication did not complete. A subsequent bounded retry exceeded the outer process timeout and left a stale `capture-remote-state` process, which was terminated by exact command-line match. No successful live evidence was claimed, and no live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

2026-06-05 live evidence status: successful. After operator-observed fresh Cl@ve auth succeeded, the full 2022-2026 read-only remote-state capture reused the persisted session. Filed-history succeeded, wallet/cartera succeeded, the aggregate report captured 12 filed-history rows and 12 calculation observations, and profile-local reload reported 12 IVA history rows, 8 carry-forward lots, and 2 authority decisions. This does not close S56 because S56 is the standing opt-in live verification and privacy guard. No private financial values are copied into this audit, and no live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-056 | HIGH | RESOLVED | S91 bounds Cl@ve cleanup after live IVA auth timeout

The live retry exposed a production-readiness failure: after an outer timeout, the `capture-remote-state` child process could remain alive. S91 hardens the Cl@ve cleanup path by enrolling `AEAT_BROWSER_CLOSE_TIMEOUT_MS` as a centralized `Settings` field and `.env.example` entry, then routing Cl@ve browser context and browser-session cleanup through bounded close helpers. The regression tests use the existing BrowserSessionLike stand-in style to prove hanging context/session close coroutines return within the configured cleanup timeout instead of blocking the auth command indefinitely.

Validation passes for the full Cl@ve provider test module, the timeout/settings alignment tests, env example alignment tests, Ruff on the touched auth/config surfaces, and vault plan check. This is local cleanup hardening only; no successful live evidence was claimed, and no live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-038 | LOW | REVIEW-PASSED | S70 reconciliation and downstream export routing is covered by current code

The S70 review inspected the reconciliation classification tests, Modelo 303 engine integration tests, export gate tests, injected decision repository coverage, and export provenance implementation. Current coverage classifies persisted AEAT wallet evidence against local recurrence, blocks unresolved or filed-history-only states before calculation/export persistence, accepts wallet_only through the fichero export path, records redacted wallet authority provenance, and keeps live read-only verification tracked separately under W06.P15.S56. No new code was required for S70. Focused reconciliation, Modelo 303 engine integration, and export tests pass with ruff and test-shortcut scans clean. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.

## WALLET-041 | MEDIUM | RESOLVED | S73 constants inventory left portal catalogue and Cl@ve script literals for S74/S75

The S73 AST inventory excluded tests, docstrings, and the central external-constants module, then scanned non-test Python modules for volatile AEAT/Sede route and host tokens. The existing centralization tests pass for current live Sede executable routes, manual/oracle auxiliary routes, and live action labels.

Remaining findings are not wallet-specific blockers, but they are still centralization work:

- `src/aeat/domain/portals/_entries`: 41 portal catalogue route literals under `/Sede/` or `/wlpl/`.
- `src/aeat/domain/portals/_categories.py`: 6 AEAT host enum literals.
- `src/aeat/domain/portals/_metadata.py`: 1 portal metadata regex/error string for `/Sede/procedimientoini/G...shtml`.
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`: 1 JavaScript snippet containing the `ObtenerClaveMovil` browser-global token.

S74 resolves the source-of-truth findings: portal catalogue paths and filing/censo path-shape rules now live under the typed external-constants `portal_paths` table, `PortalHost` values are stable registry keys rather than hostnames, portal metadata validation resolves hostnames through the central AEAT domain registry, and the Cl@ve browser-global token is centralized under the Cl@ve surface. S75 now encodes the portal route/host boundary in a static guard; the broader test-tree literal classification remains tracked separately under WALLET-044/S88.

## WALLET-039 | LOW | REVIEW-PASSED | S71 persisted-decision and override readiness gates are covered by current code

The S71 review inspected the Modelo 303 engine wallet-decision binding path, lazy reconciliation path, verification readiness path, export path, file action path, and override coverage. Current coverage proves unpersisted wallet decisions cannot feed the engine, missing wallet evidence requires an explicit taxpayer override before prefill, filed-history-only evidence remains blocking, unresolved wallet divergence blocks before revision persistence, verification reports wallet findings without granting verified-complete, export refuses before file emission, and file action checks the injected profile-bound decision repository before mutating the filing catalogue. No new code was required for S71. The focused S70/S71 reconciliation, Modelo 303 engine integration, and export gate passed, with ruff and test-shortcut scans clean. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.

## WALLET-040 | LOW | REVIEW-PASSED | S72 three-year sanitized production-service regression is covered

The S72 review inspected the new three-year filed-history regression added in the S68 implementation slice. The test persists sanitized filed Modelo 303 observations across 2024, 2025, and 2026 through `IvaCompensationHistoryRepository`, reloads them through the secure repository, and invokes the production carry-forward projector. It covers multiple periods, generation, application, remaining lots, and expiry state without private taxpayer fixtures, mocks, fakes, stubs, monkeypatching, or test-side shadow services. Focused three-year coverage and the broader IVA compensation history plus Modelo 390 continuity gate pass. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.

## WALLET-042 | LOW | REVIEW-PASSED | S73 inventory is traceable and does not overclaim remediation

The S73 review inspected the inventory method, plan row, execution record, and WALLET-041 queue entry. The step is correctly scoped as an inventory: existing centralization tests pass, the non-test AST scan excludes docstrings and the central constants module, and the remaining findings are handed to S74/S75 rather than described as fixed. No code behavior changed, no live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.

## WALLET-043 | LOW | REVIEW-PASSED | S74 centralizes portal host/path authority without live AEAT contact

The S74 review inspected the external constants schema/TOML changes, the portal entry rewrite, `PortalHost` key migration, portal metadata host/path validation, CLI portal-row output, the synthetic justificante generator, and focused tests. Portal route paths and filing/censo path-shape rules now come from `external_constants.toml`, portal entry modules no longer embed executable `/Sede` or `/wlpl` path literals, hostnames are resolved through configured AEAT domains rather than enum values, and the fixture generator uses the configured Sede origin plus CSV verification URL. Focused portal/external-constants tests pass, Ruff passes on the touched surfaces, and the non-test portal literal scan is clean. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-044 | MEDIUM | RESOLVED | Broad test-suite AEAT/Sede literals classified before broad guard expansion

The expanded AST inventory intentionally included test modules after S74 and found 224 remaining AEAT/Sede host/path string constants in test expectations, parser text fixtures, remote-state safety canaries, redaction cases, live-driver tests, and the current centralization guard test itself. This is a real centralization gap for the wider test tree, but it is not safe to bulk-rewrite blindly: some occurrences are deliberate unsafe canaries or text-parsing fixtures whose literal content is the behavior under test.

S88 now tracks the required classification and migration pass. S75 should not broaden the static guard over the full test tree until each occurrence is either moved to configured constants/helpers or declared as an accepted literal fixture/canary. No live AEAT request was made during the inventory, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

Remote-state guard tests were the first migrated S88 cluster: configured AEAT host/path values are assembled from `Settings.external_constants()`, deliberate unsafe host/path canaries live behind `aeat.tests.aeat_literal_fixtures`, and a narrow static guard prevents `test_remote_state_guard.py` from reintroducing inline AEAT/Sede URLs. At that checkpoint the broad AST inventory dropped from 224 to 177 remaining literals after excluding the declared fixture boundary; the remaining clusters were resolved later under WALLET-052.

The direct Sede/browser/auth test cluster was the second migrated S88 cluster: declarations register/cotejo tests, NIF-IVA auth-gate/oracle tests, browser site-health/session tests, persisted auth storage-origin tests, and Playwright certificate-origin tests assemble executable AEAT origins and paths from `Settings.external_constants()`. The touched subset had no remaining executable AEAT URL/path literals, passed 201 focused tests, and passed Ruff. At that checkpoint the raw AST inventory was 182 literals across 68 files when central guard self-tokens, docstrings, parser text fixtures, and declared canaries were included. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

The live application/CLI censo and notifications cluster plus the outbound Sede parser/storage/live-driver cluster were migrated next: censo G313 snapshot provenance, notification summary/query provenance, CLI censo/ratio snapshots, outbound notification parser URLs, G313 launcher/cookie-domain checks, GROI oracle structure checks, parser base URLs, observation-store provenance, GROI live form-action checks, and browser-error Renta payload URLs all resolve through `Settings.external_constants()`. The touched subsets passed 56 application/CLI tests, 46 outbound Sede tests, and Ruff. At that checkpoint the raw AST inventory was 153 literals across 55 files when central guard self-tokens, docstrings, parser text fixtures, and declared canaries were included. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

The live-parity, GROI, and NIF-IVA oracle contract cluster was then migrated: valid AEAT read hosts and paths come from `Settings.external_constants()` or fixture helpers backed by those constants, while state-creating TGVI/PRET paths, wrong-host URLs, and unsafe path checks remain explicit canaries under `aeat.tests.aeat_literal_fixtures`. The broadened static guard covers remote-state, live-parity, GROI, and NIF-IVA oracle contract tests. Focused validation passed with 125 tests plus Ruff. At that checkpoint the broad AST inventory was 133 literals outside the declared fixture boundary; remaining clusters were resolved later under WALLET-052. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

S88 is now closed. The final executable test literal was migrated in the registry referential-integrity helper, and `test_test_suite_aeat_route_literals_are_centralized_or_declared` broadens the static guard over the full test tree while excluding the two declared authority boundaries: `test_external_constants.py` and `aeat.tests.aeat_literal_fixtures`. A stricter all-string inventory, including docstrings, now reports `TOTAL=0` outside those boundaries. Focused guard plus registry tests pass with 52 tests, Ruff passes on the touched files, and no live AEAT request or write path was executed.

## WALLET-048 | LOW | REVIEW-PASSED | S88 remote-state guard literal migration is narrow and behavior-preserving

The S88 focused review inspected the new declared test fixture module, the remote-state guard test migration, and the narrow regression guard in `test_external_constants.py`. The migration preserves the same guard behavior: valid Sede/www2/www6 URLs are assembled from the central external constants registry, unsafe/unknown AEAT host/path cases remain explicit test canaries, and the focused remote-state guard suite passes. The broad test-tree literal problem is not claimed fixed; WALLET-044/S88 still track 177 remaining literals outside the declared fixture boundary. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-049 | LOW | REVIEW-PASSED | S88 direct Sede/browser/auth test URL migration is behavior-preserving

The S88 focused review inspected `test_declarations.py`, `test_nif_iva_check.py`, `test_site_health.py`, `test_session.py`, `test_authenticator.py`, and `test_certificate.py`. The migration preserves the same tested behavior while replacing inline executable AEAT URLs with configured values from `Settings.external_constants()`: declarations listing and cotejo URLs, NIF-IVA verification and 4033 auth-gate URLs, Sede site-health probe URLs, persisted storage-state origins, and Playwright certificate origins now share the central schema/TOML authority. The focused test subset passes with 201 tests, Ruff passes on the touched files, and no live AEAT request or write path was executed.

## WALLET-050 | LOW | REVIEW-PASSED | S88 application/CLI and outbound Sede URL migration is behavior-preserving

The S88 focused review inspected the live application censo/notification tests, CLI censo/ratios tests, outbound notification parser tests, G313 live-driver tests, GROI driver/live tests, parser tests, observation-store tests, and browser-error boundary tests. The migration keeps the same behavior while replacing executable AEAT URLs, cookie domains, servlet action basenames, and provenance URLs with configured values from `Settings.external_constants()`. Focused validation passes with 56 application/CLI tests, 46 outbound Sede tests, and Ruff on the touched files. At that checkpoint the broad test-tree literal issue still had 153 raw literals across 55 files; it was resolved later under WALLET-052. No live AEAT request or write path was executed.

## WALLET-051 | LOW | REVIEW-PASSED | S88 live-parity and oracle contract literal migration is behavior-preserving

The S88 focused review inspected `test_live_parity.py`, `test_groi_oracle.py`, `test_aeat_nif_iva_oracle.py`, the shared `aeat_literal_fixtures` boundary, and the broadened static guard in `test_external_constants.py`. Valid AEAT read surfaces now use configured host/path values; state-creating TGVI/PRET paths, wrong-host URLs, and unsafe-path checks remain declared canaries rather than anonymous literals. Focused remote-state, live-parity, GROI, NIF-IVA, and static guard tests pass with 125 tests, and Ruff passes on the touched files. At that checkpoint S88 still had 133 remaining broad test-tree literals outside the declared fixture boundary; it was resolved later under WALLET-052. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-052 | LOW | REVIEW-PASSED | S88 broad test literal guard closes executable-literal gap

The S88 final review inspected the registry referential-integrity helper migration, the docstring provenance cleanup, and the new broad static guard in `test_external_constants.py`. All AEAT/Sede host/path literals in test modules now come from configured helpers or the declared `aeat.tests.aeat_literal_fixtures` boundary; a stricter all-string inventory reports `TOTAL=0` outside the declared boundaries. Focused validation passes with 52 tests, Ruff passes, vault plan check passes, and no live AEAT request or write path was executed.

## WALLET-053 | LOW | REVIEW-PASSED | S88 final sweep reduces broad test literal inventory to zero

The S88 continuation re-ran the broad AST inventory and found 133 remaining non-docstring AEAT/Sede literals outside the declared fixture boundary. The remediation migrated justificante parser fixtures, portal/manual tests, registry host and live-read tests, workflow/application/live tests, persistence and SQL storage tests, CLI tests, and auth tests to configured helpers or declared canaries. Missing actual live-service paths are now enrolled in `external_constants.toml` and the typed `AeatSedePaths` schema: R210 simulator open Ajax, Renta borrador detail template, declaration consult, and Cl@ve login.

Final S88 inventory is `TOTAL=0` outside `aeat.tests.aeat_literal_fixtures`. Ruff passes on the touched surfaces. Focused validation passed across justificante (163), portal/manual (54), core/observability/SQL/session (123), application/live/filing (79), runtime-migrated storage (93), CLI (80), Cl@ve auth (37), and workflow engine (46). No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-054 | MEDIUM | REVIEW-PASSED | Modelo 100 payments-retentions construct expectation drift resolved under S90

During the S88 focused registry verification, `src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_payments_retentions_construct_excludes_atribucion_bindings` failed independently of the URL migration. The assertion expected `payments_retentions.bindings` to equal the previous-filing bindings filtered only by `"atribucion"`, but current registry state includes `renta-2025-base-liquidable-negativa-general-anterior` in the expected set while the construct does not carry it.

S90 resolved this as test expectation drift. The registry TOML was already coherent: `renta-payments-retentions` is limited to dependency classifications that target payments/retentions, while `renta-2025-base-liquidable-negativa-general-anterior` is a previous-year Modelo 100 carry-forward binding owned by `renta-anexo-c-base-liquidable-negativa-general`, not a payment or retention dependency. The repaired test now derives expected payment/retention bindings and relations from production dependency classifications and explicitly pins the base-negative carry-forward exclusion to the Anexo C construct.

Validation passes for the focused payments/retentions tests, the full `test_modelo_100_registry.py` module, and Ruff on the edited registry test file. It is not an AEAT/Sede literal centralization failure, and no live AEAT request or write path was executed.

## WALLET-055 | LOW | REVIEW-PASSED | S90 payments-retentions expectation repair is registry-coherent

The S90 focused review inspected the repaired payments/retentions construct assertions, the Anexo C carry-forward ownership assertion, the updated plan row, and the S90 step record. The implementation keeps registry TOML unchanged, derives payment/retention membership from production dependency classifications, and explicitly prevents the prior-year Modelo 100 base-negative carry-forward from being treated as a payment or retention binding. Focused tests, the full Modelo 100 registry module, Ruff, and vault plan check pass. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-045 | LOW | REVIEW-PASSED | S89 locale audit drift repaired through locale CLI

The S89 review inspected the locale catalogue changes, the use of `python -m aeat.locales set`, the step record, and the updated plan row. The notification snapshot error keys now carry concrete strings in the supported locales `en`, `es`, `ca`, and `hu`; there are no placeholder/self-reference leaves for these keys. Locale audit, locale parity tests, locale CLI tests, and Ruff pass on the touched locale tooling surface. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-047 | LOW | REVIEW-PASSED | S75 static guard now covers portal route and host literals

The S75 review inspected the new AST guard in `test_external_constants.py`. The guard scans non-test portal modules, excludes module/class/function docstrings, and allows the central host resolver while failing if portal entry modules reintroduce AEAT host literals, `/Sede/`, `/wlpl/`, or root route literals. Focused guard tests pass, the full portal/external-constants gate passes with 129 tests, and Ruff passes on the touched centralization surfaces. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-046 | LOW | REVIEW-PASSED | S76 database-backed test password guard is satisfied

The S76 review inspected `aeat.tests.secure_sql`, `test_secure_sql.py`, and `test_ephemeral_key_hygiene.py`. Database-operating tests are guarded by `test_database_operating_passphrases_use_core_test_setting`, which fails on literal `passphrase_callback`, literal `AEAT_SECRET_PASSPHRASE`, or literal `aeat_secret_passphrase` overrides when the test opens SQL-backed storage. The focused secure-SQL hygiene gate passes with 7 tests. Supplemental text scan still finds passphrase literals in pure master-key/auth/sanitizer unit tests, but those are not database-backed storage tests and remain outside this dev database password step. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-057 | LOW | REVIEW-PASSED | S94 live marker and operational access-gate inventory completed

S94 inventoried `AEAT_LIVE_TESTS_ENABLED`, `live_read`, `live_write`, `unit`, pytest hook, and access-gate usages with `rg` and `fd`, then attempted `vaultspec-rag` semantic discovery. The local inventory found the intended separation in current code: root and package pytest configuration own live-test env loading, marker taxonomy, live-read skip behavior, and permanent live-write collection drop; production live-read call sites still call `AeatAccessGate.require_live_read`, but the gate now only refuses in a pytest context when the validated setting is not the exact string `1`. Operator-facing live reads therefore proceed to the existing profile readiness, auth configuration, read-only remote-state guard, and no-submit safety checks instead of failing solely because `AEAT_LIVE_TESTS_ENABLED` is unset.

Live writes remain permanently refused by `require_live_write`, and the marker hook continues to drop `live_write` tests with no bypass. Focused validation passed with 2106 marker/gate tests plus Ruff on the access-gate and test surfaces after two incidental regressions were repaired: `test_modelo_work_ux.py` now keeps `pytestmark` before module assignments, and `test_ledger_corpus_fidelity.py` passes the EUR-normalized amount into the IVA base derivation helper instead of computing it unused.

RAG follow-up: the prior direct local-store lock ambiguity is now closed as a typed tooling-diagnostic path under S98. Resident-service searches with `--port 8766` refuse silent fallback when the service is stopped, return a typed `port_unreachable` envelope with remediation, return typed `mcp_search_timeout` when the service budget is too small, and `server service status` reports `crashed (port silent)` when the service metadata exists but the port is no longer reachable. A longer service timeout validated a successful MCP code search against the live IVA CLI/backend surfaces. Residual upstream service stability remains: a subsequent vault search saw the service unreachable, and logs showed port-binding collisions during overlapping service starts. This is no longer a silent AEAT discovery failure. No live AEAT request was made for S98, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-066 | LOW | REVIEW-PASSED | S98 typed RAG diagnostics record does not overclaim semantic discovery health

The S98 review inspected the plan row, execution record, and updated audit text. No critical or high issue was found. The record correctly distinguishes the achieved AEAT-side requirement, typed non-silent diagnostics and service-routed code search with an extended timeout, from the unresolved upstream service-stability risk where a subsequent vault search saw `port_unreachable` and status reported `crashed (port silent)`. The execution record does not claim a successful vault search, does not claim the RAG service is generally stable, and does not alter application code. No live AEAT request was made for S98, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-058 | LOW | REVIEW-PASSED | S96 live marker taxonomy rejects ordinary-test runtime env dependency

S96 added an AST-backed marker-integrity guard that rejects executable `AEAT_LIVE_TESTS_ENABLED` runtime access from ordinary unit/domain tests. Accepted runtime owners are now limited to modules marked `live_read` or `live_write`, plus focused access-gate tests that prove the env-to-settings boundary. The guard scans executable AST nodes such as `os.environ[...]`, `os.environ.get(...)`, and pytest `setenv`/`delenv`; it intentionally does not classify docstrings, README text, or error-message assertions as runtime dependency.

The ordinary cold-process CLI helper snippets in `test_cold_start_wizard_registration.py` and `test_work_calculate_row_flag.py` no longer set `AEAT_LIVE_TESTS_ENABLED=0` for local-only work-create flows. Full marker integrity passes with 2089 checks, focused cold-process CLI regressions pass, and Ruff passes on the touched test surfaces. The first combined validation command timed out and was killed by exact command-line match; smaller reruns passed. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-059 | HIGH | RESOLVED | S92 adds CLI-level watchdog for read-only IVA remote-state capture

S92 closes the local containment gap where `iva-wallet capture-remote-state` could rely on the invoking shell/tool timeout as the outermost bound. `Settings.aeat_live_iva_cli_watchdog_timeout_ms` and `AEAT_LIVE_IVA_CLI_WATCHDOG_TIMEOUT_MS` now provide a centralized top-level command budget, and the CLI wraps the combined read-only acquisition coroutine before emitting the result. When the watchdog fires, the command raises the existing typed live-IVA timeout error with `surface=remote_state_command` and a `cli_watchdog` progress context.

Focused tests prove the typed timeout classification and run a fresh Python subprocess through the watchdog timeout with a unique canary argument, then assert no process command line containing that canary remains. Settings/default and `.env.example` alignment tests pass, and Ruff passes on the touched CLI/config surfaces. Plain `uv run` validation was not used after it attempted to resync `torch` in the shared virtualenv and failed on an access-denied package lock; equivalent `uv run --no-sync` validation passed without mutating the shared environment. No live AEAT request was made, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

2026-06-04 S93 retry follow-up: the first `900000` ms watchdog default was insufficient for the operator/tool environment because the live retry command was bounded externally at 300000 ms. The shell timed out first and left a uv/aeat/python/Playwright/Chrome tree alive. The tree was killed by exact PID and temporary Playwright profile match. S92 was reopened and corrected to `240000` ms, and the settings regression now asserts the default remains below the 300000 ms live retry outer bound.

2026-06-04 containment follow-up: the corrected 240000 ms watchdog returned a typed timeout before the outer shell limit, but the first corrected run still left Chrome processes tied to a new Playwright temp profile. The CLI watchdog now snapshots preexisting Playwright temp-profile tokens and, on timeout, reaps only processes carrying newly-created `playwright_chromiumdev_profile-*` tokens. Local subprocess reaper coverage passes, and a subsequent live timeout retry returned the same typed `remote_state_command` timeout with no matching capture command, Playwright driver, or temp-profile Chrome process remaining.

2026-06-04 reopened status: later process inventory found that the previous no-stale-process claim was incorrect. A stale `capture-remote-state` command and temp-profile Chrome tree from the same read-only live retry were still running and were terminated by exact command/profile match.

2026-06-04 closeout: the latest bounded read-only retry returned normally before the 300000 ms outer command timeout, and post-run inventory found no matching `capture-remote-state` command, Playwright driver, or `playwright_chromiumdev_profile-*` browser process. This resolves the process-containment blocker only. Live acquisition remains failed under WALLET-060/S93 because both filed-history and wallet surfaces still timed out waiting for Cl@ve operator approval. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-060 | HIGH | RESOLVED | S93 live retry completed through per-year read-only slices

The post-S92 read-only live retry was attempted for Modelo 303 IVA remote state, years 2022-2026, target 2026 2T. Before the live command, the stale-process check found no prior `capture-remote-state` command. A local secure reload, which did not contact AEAT, showed 12 persisted IVA history rows, 8 carry-forward lots, and 2 AEAT wallet authority decisions for 2026 1T/2T.

The live command returned a typed failure, not a success: `auth_status=failed`, `auth_outcome=operator_timeout`, `auth_failure_mode=operator_timeout`, `auth_failure_type=ClaveMovilApprovalTimeoutError`, with both filed-history and wallet surfaces failed for the same auth timeout. Auth preflight was otherwise ready: configured Cl@ve Móvil provider, ready active profile, tax id present, provider identity present, identity alignment matches, NIE identity kind, non-QR mode, NIE support number present, persisted session present but expired, and `auth_timeout_ms=120000`. The post-run stale-process check found no remaining `capture-remote-state` command. No live read evidence success is claimed, and no AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

Reattempt status: failed and exposed a containment regression. The second S93 live retry exceeded the 300000 ms outer command timeout before the then-configured 900000 ms CLI watchdog fired. That left a uv/aeat/python/Playwright/Chrome process tree rooted in the failed command, including a temporary `playwright_chromiumdev_profile-*` Chrome profile. The tree was terminated by exact PID/profile matching. This is not live evidence success; it is the reason S92 was reopened and corrected to a 240000 ms watchdog default.

Final retry status after S92 emergency reaper: failed as live evidence, and containment remained failed. The command returned a typed `LiveIvaSurfaceTimeoutError` rendered in Spanish with `surface=remote_state_command`, `timeout_ms=240000`, and `progress: phase=cli_watchdog, surface=filed_history`, but a later process inventory found a stale matching `capture-remote-state` command and temp-profile Chrome tree from that retry. The stale tree was terminated by exact command/profile match.

Latest retry status after fresh auth: failed as live evidence, with containment now clean. `config auth login --provider clave_movil --fresh --reset-lock` returned `authenticated=True`, `fresh=True`, `reused_persisted_session=False`, and removed one persisted session. The subsequent read-only `capture-remote-state` command returned `auth_status=failed`, `auth_outcome=operator_timeout`, `auth_failure_type=ClaveMovilApprovalTimeoutError`, `filed_history_succeeded=False`, and `wallet_succeeded=False`. Redacted preflight diagnostics reported a ready registered active profile, tax-id present, provider identity present, identity alignment matches, NIE identity kind, non-QR mode, Cl@ve support number present, certificate missing, persisted session missing, and `auth_timeout_ms=120000`. Post-run process inventory found no remaining capture command, Playwright driver, or temp-profile browser process. S93 remains open because no filed-history or wallet live evidence was acquired. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

Post-S99 persisted-session retry status: failed as live evidence, with auth reuse now visible. The read-only `capture-remote-state` retry reported preflight `auth_persisted_session=present` and `auth_persisted_session_expired=False`. The command did not emit an acquisition report; it hit the CLI watchdog at 240000 ms with `surface=remote_state_command` and progress `phase=cli_watchdog, surface=filed_history`. The watchdog context reported before and after state as provider `clave_movil`, profile ready, identity alignment matches, persisted session present, and persisted session not expired, with `watchdog_reaped_process_count=0`. Post-run process inventory found no matching capture command, auth-login command, Playwright driver, or temp-profile browser process. This narrows the active S93 blocker to filed-history acquisition timing/hang while using a persisted session, not repeated fresh auth. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

2026-06-05 live closeout: the operator approved Cl@ve auth, and the persisted Cl@ve session changed from expired to not expired. The one-shot 2022-2026 capture still hit the CLI watchdog in `filed_history`, but per-year read-only captures for 2026, 2025, 2024, 2023, and 2022 all succeeded with `auth_reused_persisted_session=True`, filed-history success, wallet/cartera success, and clean post-run process inventories. Profile-local secure reload, without live AEAT contact, reports 12 IVA history rows, 8 carry-forward lots, and 2 wallet authority decisions. S93 is closed as live evidence acquired through bounded per-year slices; the one-shot full-range timeout remains open separately under S100. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-062 | HIGH | RESOLVED | S99 persisted Clave probe could dispatch a fresh phone auth request

The repeated-auth-request concern is confirmed as a real auth contract defect. `ClaveMovilAuthProvider.probe_persisted_session()` was documented to never fall back to fresh login and never trigger operator-mediated Cl@ve auth. However, when callers supplied an explicit target URL, the underlying verification path used AEAT selector dispatch for that target. If the stored session was not accepted for the selector dispatch, this could create another phone auth request while the caller believed it was only probing persisted state.

S99 resolves that contract defect for persisted-session reuse: the persisted probe now verifies the stored landing/default authenticated page without target-specific selector dispatch. Target-specific selector verification remains available through the normal explicit `verify(session, target_url=...)` path, but persisted-session probing no longer uses it. Downstream live IVA reads now either use the stored session or fail in the read surface instead of silently causing another auth request.

The live IVA CLI watchdog timeout also now records redacted local auth-session state before and after timeout, including provider, active-profile status, identity alignment, persisted-session presence, persisted-session expiry, and Playwright reaped-process count. The latest local auth test after the live timeout reported `persisted_session_present=True` and `persisted_session_expired=False`; this means the last live failure was not a missing-session failure, but a post-auth filed-history timeout before an acquisition report could be emitted.

Focused validation passed with 14 auth/watchdog tests plus Ruff on the touched Cl@ve and live CLI surfaces. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-063 | HIGH | RESOLVED | S100 one-shot 2022-2026 live IVA capture exceeds filed-history watchdog

Live evidence now shows the remote surfaces are functional and auth reuse works, but the single `capture-remote-state --from-year 2022 --to-year 2026` command remains defective for production UX. After successful persisted Cl@ve reuse, that one-shot command repeatedly times out at the CLI watchdog with `progress: phase=cli_watchdog, surface=filed_history` before producing one aggregate acquisition report.

The per-year retries prove this is not a general auth or wallet failure: 2026 and 2025 completed with zero filed-history observations, while 2024, 2023, and 2022 each completed with four filed-history/calculation observations. Each slice also completed the wallet/cartera read and reused the persisted Cl@ve session. The full-range command needs chunking, per-year budgets, progress emission, or an aggregate orchestration that persists partial-year successes before the top-level watchdog fires.

2026-06-05 implementation status: local S100 code now chunks filed-history traversal by year, aggregates the yearly filed-history reports into one command report, and scales the CLI watchdog budget by covered year count plus auth, wallet, and cleanup budgets. Focused S100 tests, broader auth/live CLI tests, and Ruff passed on the touched files. An initial live closure attempt failed before filed-history because the active profile had no reusable persisted session; that auth blocker was tracked separately as WALLET-064 / S101.

2026-06-05 live closeout: after fresh Cl@ve auth succeeded under S101, the full-range read-only `capture-remote-state --from-year 2022 --to-year 2026 --target-year 2026 --target-period 2T` command reused the persisted session and succeeded for both filed-history and wallet/cartera. The aggregate command captured 12 filed-history rows and 12 calculation observations and emitted one acquisition manifest. Profile-local reload, without live AEAT contact, reported 12 IVA history rows, 8 carry-forward lots, and 2 wallet authority decisions. Post-run process inventory was clean.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-064 | HIGH | RESOLVED | S101 fresh Clave auth timeout blocks live S100 verification when no persisted session exists

The current live blocker is explicit: after the failed full-range retry, local `aeat config auth test --provider clave_movil` reported `persisted_session_state=no_session` and provider `probe_result=ok`. That means Cl@ve identity configuration is locally valid, but no AEAT browser session is available for reuse.

A fresh `aeat config auth login --provider clave_movil` attempt then reached AEAT's non-QR Cl@ve route for the active profile, reported matching identity alignment, NIE identity kind, configured support number, a present verification code, and `failure_mode=auth_completion_timeout` after 120000 ms. The driver cannot infer the phone/app state; operator testimony is required before classifying the attempt as prompted-and-accepted, prompted-not-accepted, no-prompt, or not-checked.

Diagnostic hardening added during this pass now separates `auth_persisted_session_state` from provider `auth_probe_result`, so future live preflight output cannot imply session reuse readiness merely because the Cl@ve identity probe is `ok`. Post-failure process inventory was clean. S101 remains open until fresh auth acquisition is reliable enough to seed a reusable session and S100 can be live-verified.

2026-06-05 reattempt: the previous diagnostic `20260605T084306Z` was recorded as `app_did_not_prompt` based on operator testimony. A new `aeat config auth login --provider clave_movil` attempt failed again with `auth_completion_timeout` after reaching the same non-QR Cl@ve route and producing a verification code. The new diagnostic id is `20260605T085442Z`; phone/app state was later recorded as `operator_did_not_check`. Process inventory after the failure was clean.

2026-06-05 closeout: the next fresh Cl@ve login attempt succeeded, returned `authenticated=True`, and seeded a reusable session. S100 then reused that session for a successful full-range read-only IVA remote-state capture. This resolves the live-auth blocker for the current workflow.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-065 | MEDIUM | RESOLVED | S102 auth diagnostics show crashed before phone-state triage

While triaging WALLET-064, `aeat config auth diagnostics show 20260605T084306Z` failed with `AttributeError` because the CLI rendered `operator_report_commands` while `AuthDiagnosticDetail` did not define that field. This blocked the intended encrypted diagnostic workflow immediately after a fresh Cl@ve timeout.

S102 resolves the contract drift by adding `operator_report_commands` to the application detail model and asserting the command choices in the existing encrypted diagnostic regression. The repaired CLI now renders the redacted diagnostic detail, fingerprints, phone-state placeholder, and the allowed `diagnostics report` commands without exposing private page bodies.

Validation passed with the focused auth diagnostics test, Ruff on the touched diagnostic files, and the actual redacted `diagnostics show` command. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## WALLET-061 | MEDIUM | RESOLVED | Non-IVA CLI row validator exports restored during W10 validation

Focused W10 validation exposed a current non-IVA CLI regression: `test_work_calculate_row_flag.py` could not import `_validate_m184_share_sum` from `aeat.entrypoints.cli._modelo`. The same cold-process row path also imports `_validate_m347_threshold`. The functions had disappeared during the ongoing `_modelo` split even though the domain-owned validators still existed in `aeat.domain.modelos._row_models`.

Resolution: restored thin CLI-boundary wrappers in `_modelo.py` that filter the mixed `ModeloDetailRow` tuple and delegate to the domain-owned `validate_m184_member_share_sum` and `validate_m347_threshold` functions. The wrappers translate domain errors to `typer.BadParameter` and use localized `cli.app.modelo.work.row_m184_share_sum_error` and `cli.app.modelo.work.row_m347_threshold_error` strings enrolled through `python -m aeat.locales set` for `en`, `es`, `ca`, and `hu`. No business arithmetic was copied into the tests or CLI.

Validation: the M184/M347 validator test classes pass with 12 tests, the slow M184 revision-view regression passed separately, locale audit reports all four supported locale files clean, and the relevant row-helper names are present in `_modelo.py`. Ruff for the broader `_modelo.py` surface still reports separate duplicate rendering-helper errors from concurrent `_modelo` refactor work; that is not resolved by this row-validator repair and remains a separate codebase issue to finish or revert by its owner. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
