---
tags:
  - '#audit'
  - '#unit-log-remediation'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:3a06d268864e8fda02b01a8e2c77c818262998c2daf4dcdb5b7e33d51f060da3'
related:
  - "[[2026-10-04-unit-log-remediation-plan]]"
---

# `unit-log-remediation` audit

## Scope

Uncommitted repairs derived from `.logs/unit-tests-20261004-180702.log`, reviewed against current source and the approved plan. The run was incomplete: 270 recorded failures and a crashed worker do not establish the status of unreported tests. Other sessions are modifying this shared workspace; review and verification are scoped to assigned remediation. No tests, browser launches or services were performed. The full-remediation continuation includes canonical source compilation and generated-target publication, with actual outcomes recorded below.

## Findings

### financial-clock | medium | Wallet freshness used a different instant from the owning operation

The calculation accepted an explicit clock while persisted wallet reconciliation used ambient time. The lead now propagates one operation instant through calculation, verification, filing and export to reconciliation. Capture timestamps remain unchanged and stale-wallet refusal remains enforced. Fixtures missing a captured wallet authority source or a calculation revision now carry that evidence. Added regression cases cover the 31/32-day boundary without execution. Scoped Ruff lint/format, ty and diff checks pass for the lead's 21-file set; the explicit Python3.13 interpreter bypassed the incomplete local virtualenv configuration.

### presentation-authority | medium | Standalone PDF reconstruction consulted unbound registry facts

The embedded report records software identity grade, not current program/developer identity values. Presentation now renders that persisted grade in all four locales without requesting new authority. A regression reconstructs development-grade presentation outside the governed fact context. Envelope export passes a software identity input only where the layout declares the capability; fact-stamped record identity remains independent. Locale YAML parsing and scoped static checks pass; runtime reconstruction remains unverified.

### browser-readiness | medium | Isolated roots hid binaries and owner failure left readiness pending

Test bootstrap pins the configured binary cache before isolating private state. Native Playwright starts inherit the same cache. Readiness races the owner task with a bounded event wait, preserving early failure and ensuring cleanup. Windows supervision assertions use the canonical conservative PID liveness probe. Worker scoped Ruff, AST and diff evidence passed; no browser or test was launched.

### structural-inventories | low | Several assertions described retired source structure

Composing-write inventory now removes three guarded sites and records four delegating repository wrappers with explicit limitations: a commit fence is not a revision guard. SQLite relative URL expectations follow the canonical project anchor while avoiding checkout database creation. Ledger import permits the existing TUI door and continues to exclude MCP. The interface worker owns remaining CLI, TUI, documentation and provenance corrections.

### registry-ownership | medium | Registry semantic repairs remain with existing active source owners

The user's full-remediation instruction supersedes the earlier handoff-only outcome. This team now implements the remaining log-derived source repairs and their canonical generated companions. M303 2022 recargo binding and box 18 are corrected while later effective revisions remain unchanged; M145 accepts the official single-space ordinary-page marker. The lead owns M190 source-pinned signed-total profiles and serialized generation; the autonomous browser worker owns M180 split-total expectations and property requiredness. M130/M111 retain strict production transport parsing with the already-present one-editor-newline fixture correction. No tests run. Persistent lock sidecars alone are not treated as evidence of an active publisher.

### verification-coverage | medium | Runtime behavior is intentionally unverified

Verdict: PENDING. User prohibited test runs; new regression cases remain unexecuted, and the historical incomplete run cannot verify the changes. Source-inventory FileNotFound failures also require a stable tree, rather than suppressing missing sources during concurrent moves. Keep all verification-dependent Steps open and do not claim the suite passes.

### logging-and-errors | medium | Redaction conversions and exception ownership repaired

The logging worker supplied coupled operand/conversion scrubbing, including positional and mapping arguments, star width/precision, escaped percent and repeated handler filtering. Sensitive numeric values remain redacted. Five previously bare exception classes now have explicit registered categories and translated messages; source-jurisdiction refusal retains its semantic projection through jurisdiction_code. Production invariant raises use InternalInvariantError. Lead reviewed these changes and their catches; worker scoped Ruff, ty, AST, translation-registration and diff checks pass. New regression cases remain unexecuted.

### filing-fixture-lifecycle | low | Seeded filing now carries its actual filed revision and pointers

The lead tightened the fixture further after initial checks: PRESENTADO revision with matching verified/filed metadata, and work-unit current/filed calculation and filing pointers. Focused Ruff and ty checks passed after the adjustment. The fixture does not claim tax calculation correctness; it supplies coherent persisted lifecycle evidence for capture-history reconciliation.

### interface-integration | medium | Layout timing and declaration-origin drift repaired

Restricted-session tests previously read updated content before Textual completed layout, then clicked stale coordinates. Readiness now includes pilot layout pauses, clicks are asserted, and 80/48-column cases cover the action row's auto height and equal-width controls. Operation census now resolves module-qualified and aliased declarations by canonical origin instead of bare names; async sites retain explicit owner/reason declarations. M349 assertions identify columns semantically. CLI inventory/projection and retired localization expectations were aligned with current contracts. Docstring repairs across 88 files were checked by AST comparison with docstrings removed. Worker lint/format/AST/diff checks passed over 107 Python files; the lead completed three docstring handoffs with focused lint/format checks and repaired ledger-import TUI permission. No runtime tests were executed.

### independent-review-parent-order | high | Resolved: filing fixture initially saved child before parent

The independent Sol high review found that CalculationRevisionCatalogueRepository.save validates persisted parent coordinates, while the modified fixture saved its parent later. The lead restored initial WorkUnit persistence before the calculation save, retaining a later pointer update after both identities exist. Source review confirms the required order. Focused Ruff, format, ty and diff checks passed after correction; runtime verification remains pending.

### independent-review-identity-grade | medium | Resolved: reported grade still assumed every envelope stamps identity

The independent review found that argument forwarding was fixed but envelope_stamped_software_identity still returned an identity for no-slot envelopes. The lead now uses the same capability predicate there, so the export result and calculation-report projection agree with rendered bytes. The existing four-case M369 exterior end-to-end regression now asserts software_identity_grade is None. Focused Ruff, format, ty and diff checks passed; the regression was not run.

### final-static-review | low | Runtime and registry closure remain pending

All three autonomous worker deliveries are integrated, including their ownership handoffs. The independent review's two implementation findings were corrected and statically rechecked. No tests ran. Review verdict remains PENDING because runtime evidence is prohibited and registry-source issues remain under their existing active owners; the plan is not marked complete and no commit was made. Vault feature validation reported zero errors and warnings after template cleanup.

### full-remediation-source-review | low | Remaining financial and wire-format causes repaired

M303 2022 now supplies the super-reduced recargo binding to box 18 and the owning construct. Read-only declaration materialization confirms later editions retain their prior effective semantics; 2023 keeps its own source attribution. M145 ordinary-page validation accepts only absent or one ASCII-space marker, while C remains the complementary marker. M180 enforces required per-row casillas from the pinned revision and its tests address split integer/fraction amounts. Lead integration tightened required-value handling to refuse whitespace as well as empty strings without changing optional-field activation. Scoped lint, formatting, type and syntax checks pass; tests remain unrun.

### m190-independent-review | low | Source-pinned signed-total grammar reviewed

The independent Sol high reviewer found no actionable defect in the four M190 profiles or the source grammar. All epochs agree on sign position 145, integer positions 146–158 and decimal positions 159–160; altered sign, decimal-comma and partition clauses reach refusal paths by static inspection. The M180 guard remains scoped to its unconditional binding-row requirements and does not impose them on M190. Canonical M190 2022 target regeneration succeeded; the other epochs and active authority adoption remain in progress at this checkpoint. Review verdict PENDING reflects unexecuted runtime checks, not a remaining identified source defect.

### independent-review-clock-before-wallet | medium | Resolved: reject invalid operation clocks before wallet persistence

Sol high review found that calculation preparation and verification/filing preconditions could refresh a wallet decision before the lifecycle clock-order guard rejected the same operation. The lead moved the calculation guard immediately after work-unit loading, verification's guard before gate-findings collection, and filing's guard before precondition evaluation. The operation keeps one evaluated instant; stale evidence rules remain intact. Scoped Ruff and ty pass, formatting corrected. Regression authoring is assigned to the independent reviewer; no tests run.

### source-inventory-lifetime | low | Candidate discovery now expires with source caches

The complete 270-node audit identified cached candidate lists surviving parsed-source release. The medium worker now clears both inventories at the module boundary and aligns the lazy AST fixture with that lifetime. Strict reads still raise if a source disappears during a scan. Added regressions cover rediscovery and missing-file refusal; scoped lint, formatting, type, syntax and diff checks pass without executing tests. One browser worker crash has no Python traceback in the supplied log and remains under final static investigation.

### canonical-target-completion | low | All four M190 targets regenerated

The exact-digest canonical republish-target path completed for M190 2022 (design 2020), 2023, 2024 and 2025-y-siguientes. Each target changed the total at positions 145–160 from text to signed monetary representation with blank-or-N leading sign; generated manifests were updated by the pipeline. No generated file was hand-edited. The four temporary source-pinned drift dispositions were retired. Static target receipts are in `.logs/m190-remediation-generated-receipt.json`; scoped data syntax and diff checks pass. M303's corrected source has its current generated form. Final authority adoption is serialized behind a concurrent unrelated M714 target publication.

### complete-failure-inventory | low | 270 recorded failed nodes accounted for

`.logs/unit-log-remediation-coverage.json` maps exactly 270 unique failures to log lines, causes and source evidence. Updated source hashes and anchors validate without runtime execution. 269 nodes have source remediation identified and remain runtime-unverified; the remaining node is the worker process loss with no Python traceback. The final static browser cleanup review is still pending. This inventory covers recorded failures only, not tests the interrupted run never reported.

### final-autonomous-reviews | low | Known source findings resolved; crash evidence remains incomplete

The final Sol high integration review confirms clock-order checks precede all three wallet-refresh paths. Added calculate/verify/file regressions assert that a refused backdated clock leaves both the wallet decision and its audit history unchanged; static lint, formatting, type, AST and diff checks pass. The browser reviewer found a demonstrated real-boundary startup cancellation leak and repaired runtime retention plus cleanup across repeated cancellation, with an unexecuted real-driver regression. Static cleanup tracing found no demonstrated parent-worker kill. The log records the timeout configuration and an unclean worker exit but supplies no causal traceback or timeout dump. The crash cannot be claimed resolved by the nearby fixes.

### authority-adoption-first-attempt | low | Concurrent source mutation safely refused

The first canonical publish-authority attempt validated a candidate but refused descriptor replacement because the input receipt changed before cutover. The old active authority was preserved. Another session was advancing M714 registry targets; after checking that its current command was read-only, the lead started one fresh guarded publication against the new input state. All named M190 targets and source remediation remain complete; runtime authority adoption is not claimed until successful publication.

### authority-adoption-second-attempt | medium | Active adoption remains blocked by concurrent registry writes

The fresh second publish-authority attempt again validated and staged a candidate, then refused cutover because its input receipt changed. Concurrent processes advanced M714 2023 generation; recent writes exist in that modelo. The previous descriptor remains selected. This is an actual unresolved adoption boundary, not permission to disable currency checks or overwrite another publisher. All log-derived source repairs and four M190 target publications are complete. A focused read-only receipt review is checking whether incidental metadata also contributes before deciding whether another stable-input attempt is justified.

### archived-worker-evidence | medium | Late evidence identifies the crash-triggering readiness hang

The lead inspected the run archive referenced by the supplied log, including `artifacts/product-logs/pid-26908/cadrumo.log`. Its gw4 paths identify the affected worker. The final entry at 18:30:10.071 records `browser_not_provisioned` for profile `cancelled-authenticator`; BrowserSession immediately raises BrowserError on that path. The original test created an owner task, then awaited authenticated.wait() without observing the owner or imposing a deadline. Authentication failed before authenticated.set(), so the parent could wait indefinitely. The configured 300-second timeout and installed Windows pytest-timeout thread implementation calling os._exit(1) support the ensuing worker-loss explanation, although no timeout dump proves the exact exit instruction. Existing cache pinning plus failure-aware bounded readiness repair this demonstrated path. This new archived evidence supersedes the earlier diagnosis-incomplete classification. All 270 recorded nodes now map to source remediation; all remain runtime-unverified.

### publication-receipt-diagnosis | medium | Final adoption refused on concurrent lock metadata

A third instrumented canonical publication preserved all guards and captured before/after receipts. `.logs/unit-log-authority-publication-receipt.json` shows equal content-based source identities (`41e3d32263268e5ff0c2d6d805a07634bb181a235d53ecff62decd41921d759e`) but a changed walked registry identity: another transaction created `.generated-export-transaction-714-2024.lock` and changed the registry root directory mtime. The canonical compiler refused this unstable receipt. No authority descriptor was replaced and no guard or lock sidecar was removed. Source changes and all four named M190 generated targets are complete; final active adoption remains blocked by concurrent registry transaction activity. No tests run.

### Iteration over the completed 120-failure run

The completed run `.logs/unit-tests-20261004-212139.log` recorded 120 failed, 27,927 passed, 151 skipped; no worker crash. User explicitly authorized test reruns and full remediation. Failure traces are indexed in `.logs/unit-rerun-120-traces.json`.

Root-cause clusters include native operation-channel admission and incomplete native fault ports; stale interface fixture inventories and missing persisted calculation/profile evidence; canonical country/currency/year/parser/hash contracts; M303 fixture carry divergence; typed M180 wire-policy assertions; stale active registry authority; retired invoice-retencion refusal keys; and remaining M369/M100/M130/receipt/wallet fixtures. Independent autonomous workers own disjoint clusters.

The M303 shared fixture authored arbitrary previous-period compensation conflicting with its EUR 1,200 wallet. It now authors explicit matching filed evidence; export provenance asserts the matched wallet, recurrence, and filed observation sources. The guard remains intact. `.logs/iteration-120-export-wallet.log`: 64 passed. M180 split monetary parser assertions now check ParsedExportPolicyWireValue and emitted bytes; `.logs/iteration-120-replay.log`: 26 passed, three M190 failures against the previous active authority.

Canonical authority publication succeeded on retry without bypassing receipt checks: `.logs/iteration-120-authority-diagnostic.log`; logical generation `7ea7a1a5903e4d2ac229b5c21f0275dd9bb5f464c0940af56e3e35fe5a2c4984`, database `authority-d53af6737623075b8dd65f5875bf6b556b5e09d0eb3340bc3cde1906115f678b.sqlite3`. The diagnostic records unchanged candidate receipts. Earlier refusal due changed inputs was preserved. M347 identifier source migration will require another generated-target publication and authority adoption.

Worker evidence: runtime cluster and adjacent ownership regressions 135 passed (existing markers excluded 15); interface 34 unique passing tests; structural cluster 131 distinct passing tests with one coordinated M347 identity migration remaining. See `.logs/runtime-iteration-*`, `.logs/interface-iteration-*`, `.logs/structural-iteration-*`. These scoped checks do not yet constitute a clean full-suite rerun.

### Published-authority verification | low | Registry adoption cleared source and report failures

`.logs/iteration-120-published-authority.log`: 66 passed, one M190 assertion failed. All seven previously failing M303 source-mesh nodes, two M190 contact roundtrips and the M303 calculation report passed against the refreshed authority. The remaining M190 assertion expected absent descendants where the declared optional unsigned-integer slot uses zero fill. The bundled official 2025 M190 design, page 2 (extracted lines 53–57), explicitly requires absent numeric fields to be filled with zeros; fixed_width_parser.py preserves zero when it is a valid field value. The assertion now checks Decimal zero and exact positions 723 of both 500-byte perceptor records. Its immediate rerun encountered the temporary M347 old-authority/new-row-field decode mismatch while coordinated publication was underway; no passing evidence is claimed for that rerun.

`.logs/interface-iteration-03.log`: all 48 capture-history, pull/calculation parity and recargo cross-period tests pass. Same-CSV fixtures now assert truthful unverifiability while preserving the existing confirmed receipt, filing, and audit history. M347 authored provider/map/Python/locale identifiers have been renamed together and canonical generated-target publication is running. Full suite remains pending until publication and independent review complete.

### Integrated review | low | No omitted failure or high-severity defect identified

Independent review found no high/critical issue in runtime channel admission, currency refusal translation, retired locale-key inventory, M303 matching/divergent carry fixtures, M180 exact split bytes, or source-scoped M369 blank/C rendering and read-back. All 120 original nodes are accounted for; scoped replacement/current-node evidence covers 115, with one M190 and four M369 nodes awaiting post-M347-adoption verification. M369 codec/legal-form/M100 checks: 29 passed; M130 two negative-result cases and NACE passed in the focused financial run.

M347 canonical `publish-target` correctly refused changed semantic-map provenance. Lead declared an exact source-pinned one-record migration, used `republish-target` with reviewed manifest SHA `abc8dbbaa027564f1e1f7dc145e2eaba769aea1e461230758caf5d9c47ac0715`, and retired the disposition after success. `.logs/iteration-120-m347-republish.log` records success. The semantic comparison against `.logs/iteration-120-m347-wire-baseline.json` proves all four generated TOML documents are unchanged except `community_vat_number` becoming `community_iva_number`; wire positions, casillas and row repetition are preserved. Canonical final authority publication is now running. Final verdict PENDING until the five affected cases and full unit lane complete.

### Final adoption and deeper assertions | low | M190 complete; M369 iteration continues

Canonical authority publication completed: generation `be79d7dfce199013af9b628143a6628b3fa060dd6fb3f59715b71e02077e944a`, database `authority-e64fe2d1552a2f202f77123d7a70244b6ea02e005d9e0c9a1376a1b08ffc8840.sqlite3` (`.logs/iteration-120-final-authority.log`). The five previously blocked cases then reached later assertions. M190's retained-tax control total is also split by DR190 at 161–173/174–175; parser assertions now check its typed components and exact bytes. The entire replay module passes: 29 tests in `.logs/iteration-120-replay-final.log`.

M369's official envelope period uses 1T–4T, while the body period uses 01–04. The end-to-end tests now distinguish those source-defined encodings. Their next assertion exposes optional-page inclusion requiring further adjudication. `.logs/iteration-120-final-five.log` and `.logs/m369-final-exterior-e2e.log` preserve these intermediate failures. Full unit lane has not started; the command was gated on the focused cases passing.

### Focused closure | low | All original failures covered; full rerun started

M369 source adjudication established required T36901–T36903 pages, with empty correction groups filled entirely with spaces under DR369 general notes 6–7. The actual numeric-absence codec defect is corrected using canonical source metadata; populated zero still renders numeric zeros and required missing amounts still refuse. `.logs/m369-final-green.log`: 34 passed including all four Exterior e2e cases. Existing codec tests passed all 158 cases in the preceding run. The entire M180/M190 replay module passes 29 tests. All 120 original failures now have passing focused current/replacement coverage.

The initial import-boundary run retained all 15 architecture contracts and loaded all 4,402 production modules, but reported four hard findings and a changed-tree operational refusal. Two concurrent fixture imports were already corrected; lead moved the M369 private parser checks into their owning domain package and replaced raw_key_writer's re-exported constant import with the canonical core owner. `.logs/iteration-120-test-boundaries.log`: 19 passed; scoped Ruff/format/ty passed. The fresh import-boundary check is `.logs/iteration-120-import-boundaries-final.log`.

The full `just test-unit` rerun is now running with the original lane selection, output `.logs/unit-tests-remediation-20261004-final.log`; its result and final review remain pending.

### Integrated rerun follow-up

The full rerun exposed one stale provisioning assertion after concurrent desktop webview cache enrollment: it required every cache directory to be under cache/. The repaired test requires exactly the taxonomy-declared cache directories and their parents, rejecting any additional state directory. All 16 provisioning tests pass in .logs/iteration-120-provisioning.log; scoped Ruff, format and ty checks pass.

Three InventoryLedgerRepository source-inspection failures returned isolated docstring/signature lines from inspect.getsource after inventory.py changed during the long-lived worker process. Current source retains all three _storage.mutate calls. A fresh-process rerun of all 13 singleton routing tests passed without changes (.logs/iteration-120-singleton-routing.log). This is concurrent source drift, not evidence of lost revision guarding. The full rerun remains active.

### Full rerun and crash recovery

The full `just test-unit` run ended with 6 failed, 27,995 passed, 152 skipped, 40,573 warnings in 2,899.95 seconds (.logs/unit-tests-remediation-20261004-final.log). It was INCOMPLETE: worker gw5 died in the recorded-output redaction sweep, leaving 133 collected nodes without outcomes. Five reported failures were already adjudicated: one stale cache-directory assertion (fixed; 16 tests pass), three inspect.getsource inventory drift failures (13 tests pass unchanged in a fresh process), and a registry-enforcement scan comparing newly moved inventory error classes against an old imported registry (5 tests pass unchanged in a fresh process).

The sixth failure exposed two corpus-test scaling defects. Exhaustive substring recovery per digest would attempt about 2.3835 quadrillion hashes over the current recordings; one line has 507,761 characters and 9,230 digest markers. New test-owned recovery aligns preserved output literals and verifies candidate span digests, distinguishing existing digest text. A terminal replacement derives its endpoint directly and hashes once. No production redaction pattern, identity authority, timeout, or redaction floor is weakened. Independent high-agent review identified and verified the terminal-span correction; it found no further actionable issue. Adjacent digest alignment retains a theoretical long-span search cost; actual current identity spans are short, and ambiguous truncated-digest matches fail closed.

The first focused attempt still timed out with the stack in repeated authority lease/database identity checks. The corpus module now requests the existing authority_operation fixture, pinning one real published generation across its sweep. The recorded corpus then passed in 136.76 seconds under the unchanged 300-second timeout. All population cases passed. A new 508 KB negative regression initially exceeded Windows' environment-variable limit through its implicit pytest ID; short explicit parameter IDs correct that test-authoring issue. All 12 recovery-helper cases pass (.logs/iteration-120-redaction-oracle-final.log). A consolidated fresh-process check of all six failure paths is now running. An autonomous worker is collecting current unit-lane nodes without full-run outcomes and executing them serially.

Import iterations repaired canonical storage-mode consumers and moved prorrata fixture imports. The last completed scan loaded all 4,405 production modules, kept all 15 contracts and had zero hard import violations, but source mutation during the scan prevented overall certification. Scoped storage/prorrata checks passed 41 tests with 2 existing POSIX-only Windows skips; separate storage-management checks passed 10 tests. Final source-stable verification remains pending.

### Recovery completeness and final integration

`.logs/iteration-120-final-failures-green.log` passes all87 tests across the six failed paths and new redaction regression cases in189.98 seconds, exit0. Independent review found no remaining actionable issue in the scoped fixes.

The autonomous serial recovery completed with145 passed,1 existing POSIX-only Windows skip,0 failures in734.49 seconds. All146 selected nodes have outcomes. `.logs/iteration-120-unreported-manifest.json` and `.logs/iteration-120-unreported-results.json` retain selection and completeness evidence. Current collection had28,300 nodes versus28,286 in the original run (net14 new); original collected node IDs were not retained, so new nodes cannot be conclusively distinguished from never-started nodes. The one excluded missing node, recorded work-unit naming, passed in lead's87-test run. No selected missing-outcome node remains unverified.

A later import scan found a concurrent storage-vector test crossing from core into dev.packaging. Its owning workstream relocated the module into dev/packaging/native/tests before lead's attempted edit; no lead relocation was applied. Verification at the new location passed42 tests with1 existing POSIX skip (`.logs/iteration-120-storage-vector-boundaries-final.log`). The last source-boundary certification is being retried after that move. Earlier changed-tree refusals and transient failures remain recorded rather than rewritten as passing.

### Final verification disposition

All 120 original failures have passing focused current/replacement coverage. The later incomplete full rerun recorded 27,995 passed, 6 failed and 152 skipped. All six failed paths now pass together in an 87-test fresh-process run. Serial recovery passes 145 tests with one existing POSIX-only Windows skip; all 146 selected nodes reported outcomes. The one missing node reserved for lead ownership also passed in the 87-test run. The relocated storage-vector suite separately passes 42 tests with one existing platform skip. No known test failure or selected missing outcome remains.

Final import evidence: `.logs/iteration-120-import-boundaries-verified.log`, run `20261004T215240.759110Z-check-import-boundaries-3200-c9005d87`. Zero hard findings, all 15 architecture contracts kept, 10,292 files in both graph censuses, all 4,406 production modules loaded successfully. Exit 7 is solely an operational refusal: the governed source snapshot changed from `684e19975af53dc7bccdc8e1308a7222dafc994b87f306215f08357f8a53a721` to `21987e3d85760201a5020688dcd3d742e051e65cb752ad02fc603bc72cf2a863` while another workstream edited the shared tree. No lead source edits occurred during this attempt. The scan is not certified passing; no guard was bypassed.

Scoped independent reviews have no outstanding actionable findings. Implementation steps S01, S02, S03, S05 and S06 are closed. S04 remains open solely for source-stable integrated import certification. This is an explicit external-state verification gap, not a remaining identified source defect. No commit was made.

### 2026-10-05 resumed verification

The user requested continued fixing. Exact node reconciliation in `.logs/remediation-resume-coverage-20261005.json` accounts for all 120 original failures: 110 identical node IDs have passing outcomes, six have explicit passing renamed/expanded replacements, and four retired invoice-retencion locale-key assertions have no remaining producer or catalogue entry. No original failure is unaccounted for.

The fresh live import scan (`.logs/remediation-resume-imports-20261005.log`, run `20261004T220451.865352Z-check-import-boundaries-70508-23ac8074`) found one new concrete PRIVATE_CROSS_PACKAGE violation: CLI test `test_censo_import_fact_payload.py` imports `_certificado` from the domain certificate test module. A high-agent autonomous repair owns the shared fixture extraction and affected tests. The scan kept all 15 architecture contracts and loaded all 4,406 production modules, but concurrent edits changed 20 source files during the attempt and invalidated its graph census/source snapshot.

To obtain reproducible certification without halting other workstreams, a separate autonomous medium agent owns an isolated copy of governed source/configuration and required resources under `.logs/remediation-snapshot-20261005*`, with a captured-file manifest and the canonical import gate. Certification will apply explicitly to the captured snapshot; it will not be represented as a pass for later live-tree changes. Lead owns integration, audit updates and any current-source fixes; no guards or ratchets may be bypassed.

### Certificate fixture ownership repaired

The resumed scan's private cross-package import is repaired. `domain/censo/tests/certificado_builder.py` now defines the public typed `build_certificado` helper, and both the domain certificate tests and CLI fact-payload tests import it directly. The extracted fixture retains the original certificate values and all six override axes; existing behavioral assertions remain intact. Both affected modules pass all 12 tests (`.logs/remediation-censo-tests-20261005.log`); scoped Ruff, formatting, ty, diff and fixture AST-equivalence checks pass (`.logs/remediation-censo-static-20261005.log`). Lead reviewed the helper and both consumers with no actionable finding. Snapshot import certification remains in progress.

### Captured-source verification scope | low | Consistent inputs obtained; gate result pending

The independent capture converged on its second whole-input reconciliation: 19,524 files, 610,147,283 bytes, no final-pass source drift or copy races. Its manifest records the first pass's drift rather than hiding it. Lead verified that all three repaired certificate-fixture files are present with hashes matching their reviewed live contents. Capture is a reconciled byte copy, not an atomic filesystem snapshot; binary resources excluded from this static/loadability scope are enumerated. The wrapper invokes the unchanged canonical import gate with an explicit captured root/configuration and captured first-party PYTHONPATH, validates captured hashes before and after, and records shared dependency and subsequent live-source limitations. No certification outcome is asserted yet.

Lead also rechecked the retained SHA256 values for the original 120-failure inventory and all three result logs used by the exact-node reconciliation; all four match. The redaction recovery review remains applicable: literal alignment and digest verification preserve the no-overredaction oracle, and the real operation authority fixture removes repeated per-candidate leases. No new actionable finding arose. Final review remains PENDING solely for the canonical captured-source gate result.

### Failure concentration | low | Shared contracts explain the broad failure surface

The original 120-node inventory spans 30 test modules. Its largest concentrations are 28 profile-worker cleanup cases, 14 CLI runtime-fixture cleanup cases, 23 export-output cases, seven source-mesh ledger cases and five revision replay cases. These counts are module concentrations, not independent root-cause counts. The two runtime cleanup modules alone account for 42 failures (35 percent), supporting repair of shared native admission/fault-port and cleanup ownership contracts rather than individual assertion changes. The financial clusters similarly depended on coherent wallet/filed evidence, adopted registry authority and source-defined wire encodings. Later inspection-only failures caused by concurrent edits passed unchanged in fresh processes; the redaction worker crash required a separate algorithmic and authority-lease correction.

### Captured gate findings | high | New corpus-tooling test dependencies require repair

The first captured-source gate failed. Its loadability census refused stale generated targets; lead regenerated the live aggregate and partitions using `python -m dev.quality.import_load_probe --compile-targets` (exit 0, `.logs/remediation-import-targets-20261005.log`). Comparison against the captured inventory removes five deleted production-module entries. No metadata was manually authored.

The graph also found six direct occurrences across five domain test modules importing newly relocated `dev.corpus.text`, producing transitive failures in five architecture contracts. A fresh autonomous high-agent assignment owns coherent consumer/test-support relocation or repair, preserving the other workstream's corpus move, the canonical parser, and all behavioral assertions. Scope: registry test support `authored_editions.py` and `legal_quotation.py`, IVA tests `test_rate_grounding.py`, `test_spanish_territory_grounding.py`, `test_supply_nature.py`, and strictly necessary direct consumers. No dynamic-import bypass or ratchet change is permitted. These are new captured findings, not reclassifications of the original 120 failures. S04 remains open; final review is REVISION REQUIRED until this concrete dependency defect is repaired and the captured gate passes.

### Concurrent corpus repair and fresh regression evidence | low | Existing repair preserved and verified

The corpus ownership repair landed through another workstream before the assigned worker edited it. No lead/worker source relocation was applied. Generic normalization now has its canonical core owner; the two extracted-unit-dependent IVA test modules live under `dev/corpus/tests`. The three IVA test bodies are preserved by AST comparison. Independent focused verification passes 120 tests (`.logs/remediation-corpus-consumers-focused-20261005.log`), with scoped Ruff/format/ty checks passing. The broader selection recorded 120 passed and three setup errors caused by unrelated M720 authored/generated target inconsistency (`.logs/remediation-corpus-consumers-20261005.log`).

A new run selects all 116 surviving original/replacement cases plus the complete remaining locale-refusal guard module. It has exposed two M180 replay assertions stale against changed semantic decoding: the parser returns the recombined Decimal total, while the assertions still expect physical policy fragments. Autonomous high-agent adjudication owns this contract repair, retaining independent totals and exact wire assertions.

Captured attempt 0002 additionally exposes one missing ErrorCode registration for `OperationFinancialOperandRefusedError` and one capture-resource omission (`dev/packaging/release-python-version`). A medium agent owns current-source registration verification/repair. Lead expanded the next capture to include the actual extensionless resource, without changing product code or weakening the loadability check. The runner now uses the captured owning `write_load_target_inventory` API after canonical authority preflight, rather than reconstructing generator selection itself.

### M720 structural republication | low | Exact existing migration identified

M720's authored mapping and bindings removed five duplicate manual identity/year inputs, but the generated two-record export and generated form companion still reference them, causing nine structural validation findings and three unrelated registry-test setup errors. The existing source-pinned disposition authorizes exactly two changed records under source SHA `ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7`. Independent review confirmed the official fields/positions and the canonical generated-form companion route. Lead retained the old outputs in `.logs/remediation-m720-baseline-20261005` and is using the existing digest-bound publisher, not manually editing generated targets.

The initial check lacked the reviewed manifest and a first replacement attempt used 2025; both were refused. The accepted repair witness is explicitly 2024/0A, with old manifest `1217b488e839465f1499fba090eeab3faa1e39e83068d7447de68467427f398d`. The exact witnessed replacement is in progress. All refusals remain preserved.

Independent review also identified broader pre-existing M720 semantic concerns: type-2 declarado NIF/name remain independent manual inputs despite source equality requirements, and generic name encoding does not establish the source's uppercase/diacritic/name-order contract. Those fields/formatting policies are not being expanded by this narrow structural regeneration; target currentness will not be claimed as complete legal/tax conformance. Preserve these findings for the owning M720 workstream rather than silently treating regeneration as their correction.

### Latest replay, registration and M720 closure | low | Focused verification passes

The fresh original-case selection finished with 148 passed and three stale M180/M190 replay assertions. The semantic decoder now recombines adjacent money components into Decimal totals; the repaired assertions retain independently specified totals, fractional cents and exact wire bytes. Full replay, unsigned-component and export-policy coverage passes 310 tests (`.logs/remediation-replay-split-money-20261005.log`), with scoped static checks passing.

`OperationFinancialOperandRefusedError` now has its defining ErrorCode registration, nonretryable REFUSED category and canonical messages in four locales. Real recorded-envelope regression coverage passes 14 tests (`.logs/financial-operand-registration-tests.log`); a fresh process resolves all 11 refusal reasons in all four locales. Scoped Ruff, formatting, ty and whitespace checks pass. No feature behavior or guard was weakened.

The M720 publisher's old-manifest guard correctly refused lead's exact replacement because another workstream had already published the repaired target. Lead installed no generated files. The current target passes canonical target-current (`.logs/remediation-m720-current-20261005.log`, exit 0); `.logs/remediation-m720-comparison-20261005.json` proves exactly five source-owner changes with other field policy, geometry, literals and record encoding preserved. The other workstream also retired the fulfilled disposition; the live ledger now has no rows. Updated registry tests distinguish literal prefixes from manual bindings at positions 58/18, retain the position-480 boundary, and pass all 35 selected unit/integration tests including the three prior setup errors and eight numeric-profile tests (`.logs/remediation-m720-verification-20261005-all-lanes.log`). Scoped static checks pass. Lead reviewed these assertion changes without an actionable finding. The pre-existing M720 semantic caveats above remain outside this structural repair.

Captured attempt 0003 is running with the actual packaging version resource and completed error-registration/replay fixes. S04 remains open until its final integrity and canonical gate verdict are available.

### Captured attempt 0003 | high | Two newly captured private test imports require repair

Attempt 0003 completed with exit 1 and unchanged captured hashes before/after. All 4,407 configured non-test modules loaded, all 15 architecture contracts were kept, both graph censuses contain 10,299 files, and approved architectural debt is zero. Two hard findings remain: `test_typed_financial_operand_custody.py` imports private `_Baseline` and `_Batch` test-support symbols across packages. These newly captured consumers were absent from the previous failing population. Autonomous medium-agent ownership is restricted to the consumer, defining test support and necessary direct test consumers, with focused tests and no production/ratchet bypass.

The 19,537-file capture's canonical metadata generation reproduced all five live inventory documents byte-for-byte. `.logs/remediation-final-scope-hashes-20261005.json` verifies that all 13 checked latest repair/resource files matched captured contents. Four unrelated live paths changed during the run and are explicitly listed in the verification artifact. The stable result is a real remaining test-support defect, not an operational source-mutation refusal. Final review remains REVISION REQUIRED; S04 is open.

### Fresh original-failure reconciliation | low | All 116 current cases pass

`.logs/remediation-fresh-original-coverage-20261005.json` reconciles actual recorded call-phase outcomes from the new 148-pass/three-failure run and the subsequent passing 310-test replay run against the original exact-node mapping. All 110 unchanged nodes and six explicit replacements have latest PASSED outcomes. The four obsolete locale-key assertions remain separately justified retirements; zero original failures are unaccounted for. The artifact retains SHA256 values for both result logs and the original coverage manifest. This closes original-node coverage without treating the incomplete full-suite run as green. The only current review blocker is the two later captured private test-support imports.

### Financial-custody test support | low | Private import repair verified

Moved the two synthetic strict models into the public defining `application/operations/tests/financial_operand_models.py` and changed both contract/custody test consumers to import their public names directly. The field/configuration contracts and behavioral assertions remain intact. All nine affected unit tests pass (`.logs/remediation-financial-custody-fixtures-20261005-tests.log`); scoped Ruff, formatting, explicit-environment ty and whitespace checks pass. Lead reviewed the defining module and both consumer deltas. Concurrent migration from concrete model-name identity to the canonical schema-identity factory is preserved, not attributed to this fixture extraction. No production behavior, import guard or ratchet changed. Canonical inventory regeneration and captured gate attempt 0004 are now running; final review is PENDING its result.

### Concurrent Google acquisition retirement | low | Captured intermediate consumer state identified

Attempt 0004 retains unchanged captured hashes, 4,404/4,404 module loads and all 15 kept contracts, but reports 32 missing targets/symbols from Google evidence-acquisition tests. The accepted `2026-10-04-google-app-identity-adr` commitment 5 and approved plan S02 intentionally withdraw Drive acquisition, evidence pull/pull-all and document-link choices while preserving local evidence intake and stored-history vocabulary. This is an independent active feature migration, not a reason to resurrect removed APIs.

By live inspection the owning workstream had already removed or updated every reported old reference: 12 diagnostics point to removed consumers, 16 old symbol spellings are absent and four old module spellings are absent (`.logs/remediation-google-captured-findings-live-status-20261005.json`). This spelling comparison is triage, not a substitute for canonical verification. Lead made no Google/core source edits. Current retained Drive-reference/owned-entry tests pass all 42 cases (`.logs/remediation-drive-refactor-verification-20261005.log`). An autonomous high worker verifies the application/interface consumers against the accepted withdrawal and preserves concurrent changes. Captured canonical attempt 0005 is running; final review remains PENDING. Earlier 0004 failures remain evidence of the captured intermediate state.

### Retained evidence-ingestion verification | low | Concurrent migration passes without further edits

The autonomous high worker found the assigned consumers already migrated by the owning Google workstream. All seven assigned paths stayed unchanged during verification. The retained canonical operation is `ledger.evidence.batch`; withdrawn sweep/folder tests follow the accepted explicit removal decision. Nineteen focused tests pass, including native CLI ingestion and shared-supervisor batch conformance (`.logs/remediation-evidence-consumers-20261005-tests.log`). Scoped Ruff, format, ty and AST checks pass; `.logs/remediation-evidence-consumers-20261005-source-state.json` retains the source-state evidence. No remediation source edits were made in this scope and no scoped issue remains. Captured attempt 0005 converged after four reconciliation passes and remains the final pending import/integrity verdict.

### Integrated remediation closure | low | PASS for the reviewed remediation and captured source

Final canonical gate attempt 0005 exits 0 with verdict `clean`. All 15 contracts are kept; both graph censuses contain 10,296 files and 77,588 dependencies. All 4,407 configured non-test modules load. Hard findings, approved/current architectural debt, pending retirement and operational failures are all zero. Graph source digest before/after is `b9d3b85aaf26afe91a0bee743bc1ab959c9275cc7c287a8418126233839a4f77`; the wrapper independently reports no captured hash changes before or after. Retained evidence is `.logs/remediation-snapshot-20261005/attempts/0005/{final-inputs.json,verification.json,gate.log,artifacts/import-health.json}`. Capture covers 19,534 source/config/resource files; all 16 checked latest repair files match it in `.logs/remediation-final-scope-hashes-attempt5-20261005.json`. Canonical metadata generation and earlier failing attempts remain reproducible and retained.

Four live paths changed after capture: typed financial broker tests, typed financial operand submission, supervised streams fixture and supervised-runtime tests. The certificate applies to captured inputs, not these later independent edits. Shared installed dependencies and the enumerated captured-resource scope remain stated limitations. No guard, timeout, ratchet or source-integrity check was weakened to achieve this result.

Review verdict is PASS for S01–S06 remediation and this captured integrated state. Fresh recorded outcomes reconcile all 116 current/replacement original cases; four obsolete catalogue assertions are separately retired, with zero unaccounted original failures. Latest focused verification passes 310 replay/component/export-policy, 35 M720, 14 registration/locale, 12 certificate, nine custody-fixture, 120 corpus-consumer, 42 retained Drive and 19 evidence-ingestion cases. These scopes overlap earlier coverage and are not a single aggregate suite count. The earlier incomplete full-suite run and successful failed-path/missing-outcome recovery remain accurately recorded. No single uninterrupted green full-suite run is claimed. Broader pre-existing M720 semantic findings remain documented outside this structural remediation. No commits.

## Recommendations

Close the remediation plan using the passing focused evidence, exact original-case reconciliation, successful crash recovery and canonical captured gate attempt 0005. No unresolved defect remains in the reviewed remediation scope. Preserve prior failed attempts and the incomplete full-suite log rather than relabeling them green. Later independent live-tree changes require their owning workstreams' verification; this capture does not certify them. The broader M720 semantic concerns remain explicitly documented for its owning workstream. No commit was made.
