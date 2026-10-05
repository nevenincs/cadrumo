---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:159a47cd9ba0af44f13138e26c855f2169d47a6be01f9cf367f5e7f4f6ffb141'
related:
  - '[[2026-10-04-reachability-burndown-plan]]'
---
# `reachability-burndown` audit: `exact zero closure review`

## Scope

Reviewed the live reachability-burndown worktree against its accepted decision,
implementation plan, exact-confidence audit, zero-target quality gates, and focused
detector-teeth tests. The review covered deletion overreach, import and ownership
boundaries, compatibility surfaces, duplicate authorities, exact finding projection,
and the ability of each closure gate to detect a planted defect.

## Findings

### unconsumed-export-teeth | high | The clean export signal is not backed by a passing planted-defect control

`dev/quality/unconsumed_export_coverage.py:66` chooses repository-relative identity
whenever the supplied tree happens to live below the repository, while
`dev/quality/tests/test_unconsumed_export_coverage.py:24` constructs the expected
identity relative to the supplied package root. In the repository-configured pytest
scratch tree those identities differ, so the positive detector-teeth case at line 28
returns no finding for a declared unused export. The focused suite exits 1 with one
failure and eight passes. Consequently the live `unconsumed-export coverage: no
findings` result is not sufficient closure evidence: the gate's positive control is
red at the exact point where it must prove that zero is meaningful.

Validation: `uv run --no-sync pytest -q
dev/quality/tests/test_unreachable_module_coverage.py
dev/quality/tests/test_unused_symbol_coverage.py
dev/quality/tests/test_unconsumed_export_coverage.py` exits 1 at
`test_an_exact_unused_export_without_a_production_importer_is_reported`.

### exact-confidence-exit | high | An all-zero exact audit still exits nonzero

`dev/audit/unreachable_code.py:1767` preserves the unfiltered result's `FINDINGS`
outcome after removing every row outside the requested confidence tier. The CLI at
line 1921 then returns the findings status solely from that stale outcome, although its
line 1896 contract says it exits on findings and the rendered JSON contains no modules,
symbols, tests, or exact finding identifiers. The current tree therefore prints an
all-zero exact headline while the process exits 1. This is not residual exact debt; it
is lower-confidence debt leaking through the projection's status. It makes the exact
audit unusable as an unambiguous automation contract and conflicts with the plan's
requirement that audit and zero-target gates agree from one stable revision.

Validation: `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact
--json` reports 2046 of 2046 shipped modules reachable, empty `exact_finding_ids`,
empty `modules`, `symbols`, and `tests`, but exits 1.

### detector-typecheck | high | The reviewed detector surface fails strict type checking

The focused strict checker reports ten errors. Nine are in
`dev/audit/unreachable_code.py`, including deprecated `ast.Index` use at line 943 and
unknown container or AST value types at lines 969-972 and 1295-1301. One is the
partially unknown `consumed` set inferred at
`dev/quality/unconsumed_export_coverage.py:90`. Shipping the closure with these errors
would violate the repository's strict type-quality gate even though Ruff accepts the
same files.

Validation: `uv run --no-sync basedpyright dev/audit/unreachable_code.py
dev/quality/unconsumed_export_coverage.py dev/quality/unused_symbol_coverage.py
dev/quality/unreachable_module_coverage.py` exits 1 with ten errors. `uv run --no-sync
ruff check` over the same detector files and representative changed test-support files
exits 0.

No critical findings were identified. No medium or low findings were identified in
the reviewed closure contract. The three live zero-target commands for unreachable
modules, exact unused symbols plus orphaned tests, and unconsumed exports each exit 0,
but the findings above prevent treating those headlines as final closure.

### closure-rereview | low | All three high findings are resolved in the live tree

Re-review of the current tree confirmed that every previously recorded blocker is
closed. The focused unreachable-module, unused-symbol, and unconsumed-export
detector-teeth suite passes all nine tests, including the planted unused-export
positive control. The filtered exact audit now returns a `CLEAN` outcome and exits 0,
with 2046 of 2046 shipped modules reachable and empty exact finding, module, symbol,
and orphan-test populations. Targeted strict checking of the four detector modules
reports zero errors, warnings, or notes.

The live zero-target gates independently exit 0 and report no unreachable modules, no
exact unused symbols or orphaned tests, and no unconsumed exports. Whole-tree Ruff,
whole-tree Ruff formatting, and the import-architecture gate also exit 0. A concurrent
first attempt at the unused-symbol gate encountered a Windows thread-start failure;
the required sequential rerun completed normally at exact zero and exit 0, so the
transient process-resource failure is not product or detector evidence.

Validation: `uv run --no-sync pytest -q
dev/quality/tests/test_unreachable_module_coverage.py
dev/quality/tests/test_unused_symbol_coverage.py
dev/quality/tests/test_unconsumed_export_coverage.py` exits 0 with nine passes;
`uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --json`,
`uv run --no-sync python -m dev.quality.unreachable_module_coverage`, `uv run
--no-sync python -m dev.quality.unused_symbol_coverage`, and `uv run --no-sync python
-m dev.quality.unconsumed_export_coverage` each exit 0; `uv run --no-sync basedpyright
dev/audit/unreachable_code.py dev/quality/unconsumed_export_coverage.py
dev/quality/unused_symbol_coverage.py dev/quality/unreachable_module_coverage.py`
reports zero diagnostics; and the repository commands behind `check-style`,
`check-format`, and `check-imports` each exit 0.


### october-owner-cleanup | low | The current product population has exact zero dead-code findings

The 2026-10-05 review covers S01 through S29 of the approved 2026-10-04 plan, including S07's current working changes, on HEAD 86dfb5e298 plus the reviewed owned transforms. Earlier Step analysis and ledger evidence remain applicable where their owners did not change. Governing decisions are the accepted reachability cleanup, product quality boundary, Just entrypoint and defining-module import decisions, the accepted manual-edit transient amendment and its observation predecessor, and the accepted annual prorrata comparison. Concurrent manager, desktop, registry and sign-in work is outside the reviewed implementation ownership.

The retired production doors have no replacement facades or ceremonial callers. Finite corruption, storage, label, corpus and binding probes reside with their actual fixtures; active product invariants and encrypted writers retain their defining owners. Genuine missing behavior now includes licence advisories, full census previews, exact native worker identity and denial recovery, JSON envelope production, annual prorrata comparison and the complete transient edit batch. The live full-population audit at `var/s07-reachability-final.txt` reports 3219 of 3219 shipped modules reachable with no candidate, orphan, exact symbol, executable-statement or type-only populations. `just check-module-reachability`, `just check-symbol-usage` and `just check-export-consumption` pass; results are in `var/s07-module-gate.txt`, `var/s07-symbol-gate-final.txt` and `var/s07-export-gate-final.txt`. Counts are observations, not acceptance constants or inventories consumed by code.

### october-clone-review | low | All retained token matches preserve independent boundary declarations

`just audit-dead-weight`, run 20261005T021430.939987Z-audit-dead-weight-63592-e901c1e0, inspected 3220 Vulture files and 3087 jscpd production files. Vulture reports zero findings. jscpd retains all 41 raw matches at 0.09 percent: 13 declaration matches, 23 import or contained-report matches, and five conservative executable-or-unclassified leads. The structured `run.log` retains every raw span and reports zero unparsed records. Review does not convert this advisory into a fabricated zero.

The five remaining leads were read at both exact source spans. CLI core and overview specs match through their import lists and the opening of an ExecutionPolicySpec metadata declaration (`_modelo_core_command_specs.py:3`, `_overview_command_specs.py:3`). Supervisor execution and host match a concrete method signature against its TYPE_CHECKING declaration; the guarded transition body is outside the match (`_supervisor_execution.py:651`, `_supervisor_host.py:288`). Expedientes application and Sede adapter records repeat the fields required by separate inward and browser contracts, reaching a validator decorator but not its body (`expedientes_ports.py:37`, `declarations_schema.py:24`). Dependency requirement and public snapshot repeat addresses while preserving Period versus PublicPeriod (`cross_period_models.py:259`, `dependency_projection.py:34`). Asset claim and public record repeat addresses and an enum default while preserving Decimal versus PublicDecimal (`operation_dtos.py:436`, `claims.py:66`). No second business algorithm or weaker mutation authority was found in these spans. Their declarations remain live; no file identity or disposition is used to suppress them. Verified duplicated behavior was consolidated in S05 and S06 through the real publisher, capture, option, native query and diagnostic owners.

The classifier now uses columns, Unicode character conversion and exact token extents. Rebound Field, Protocol and TYPE_CHECKING names, executable defaults and annotations, default factories, unknown calls, attribute deletion and partially overlapping executable tails remain visible. The final 47 focused controls pass at `var/s07-duplication-negative-controls-final.txt`; the preceding combined reporting and legal run has 98 passes at `var/s07-reporting-and-legal-controls.txt`. Actual whole-product measurements supply acceptance evidence; synthetic controls alone do not establish product correctness. The legal catalogue loader checks authored grammar and the live population rather than frozen filenames or numeric floors. Short operative provisions remain comparable, empty resolved bodies remain indeterminate, and legal vintage evidence is not rewritten to force matches. Pytest controller output now reports its genuine xdist selection uncertainty.

### october-transient-batch | low | Manual edit custody is complete and amount-free outside the canonical value store

The reviewed product path carries the exact validated ModeloEditSubmissionV1 batch, including every intent family, through human-only volatile intake. Apply and preflight requests are amount-free version 2. The worker-private random grant and typed schema and baseline coordinates admit exactly one custody binding. Supervisor attachment refuses an existing requirement under the operation lock (`supervisor.py:288`); current-binding checks require the identical retained requirement and owned lease. Consumption, cancellation, expiry, settlement, close and bounded drain use that same authority. DELIVERY_STARTED precedes removal, acknowledgement precedes executor access, and release proves reference release rather than a committed effect. Mutable backing input and grants are cleared; immutable models are dropped without an erasure claim.

Owner-loss reconciliation reads the exact durable custody requirement and the co-transaction domain receipt by unique operation, baseline and work-unit identity; the supervisor's one-handoff-per-invocation guard supplies the handoff association. It never reconstructs values or infers success from a refreshed calculation. Legacy financial values are purged before journal hydration; failed purge refuses instead of retaining or replaying a stored edit. Safe receipts and checkpoints contain no amount or content digest. Review traced the registered executor, actual worker dispatch, storage transaction, baseline refusal, public projections and shutdown. S07 restored financial intake to the concurrently split server dispatcher, retained a completion event independently of a narrowed closure, and restored the already tested TYPE_CHECKING proof in the owned commit capture.

Applicable evidence includes S24's recorded broker, recovery, shutdown, projection-forgery, lifetime, registered-executor and refusal-settlement controls. The latest native human financial case passes at `var/s07-native-financial-rerun.txt`; ordinary bulk submission passes at `var/s07-native-bulk-final-2.txt`. They replace the earlier overloaded timeout observations without weakening deadlines. The shared receipt fixture migration is also covered by 32 binding controls and seven actual Windows worker lifecycle scenarios at `var/s07-binding-final-controls.txt` and `var/s07-human-receipt-integration.txt`.

### october-prorrata-advisory | low | The annual comparison preserves declared authority and incomplete evidence

The three previously unused rollup members now feed the accepted nonblocking declared-versus-ledger advisory. The real annual ledger window counts output bases once, preserves cash operation information separately from payment fragments, excludes inputs and declared art.104.Tres operations, and leaves uncertain deduction rights unclassified. Dated memberships use the authored registry vocabularies. Missing declaration, incomplete classification and complete divergence remain distinct; no advisory rewrites a declared value. Ledger sin-derecho also participates in missing provisional applicability. Current settlement diagnostics retain their prior authoritative order.

S07's review repaired the outer annual register-read refusal so corrupt encrypted register evidence retains the existing storage-degraded diagnostic before comparison. Real encrypted controls for both 1T and 4T prove that corruption cannot produce a false volume divergence. The connected 12-test selection passes at `var/s07-connected-repairs.txt`; S10's applicable ledger, cash, quarter-refusal, cross-revision, applicability, existing special-regime and calculation-note checks remain recorded in the ledger. The corrected published authority identity is 64578b399a91c3743178129dac23ee58dea8b9a393d98f16ad448b9fde7e2dc7.

### october-verification-coverage | low | Required quality gates pass with explicit scope and retained failed attempts

The final live `just check-style`, `just check-format` and configured `just check-types` each exit zero (`var/s07-style-final-2.txt`, `var/s07-format-final-2.txt`, `var/s07-types-final-2.txt`). The type harness executes ty, pyrefly and BasedPyright on Linux, Windows and macOS, with unchanged project scopes and no new suppressions. Exact owned Ruff and ty checks also pass. Import-boundary certification uses the unchanged canonical gate on independently captured source, canonical compiler-generated import metadata, shared installed dependencies and isolated storage and artifacts. The corrected capture includes stubs and the extensionless packaging version input. All 4412 governed non-test modules load, all 15 contracts hold, all 10315 graph files are stable, and hard violations, architectural debt and pending retirement are zero (`var/reachability-s07-snapshot-2/artifacts/import-health.json`). Capture hashes are unchanged before and after; certification does not cover later live edits.

Failed capture attempts are retained: the first omitted stubs and a packaging resource; captured type execution also inherited the live var ignore rule and produced no report. These are not counted as clean results. The applicable full configured type result is the final live run. Broader locale inventory and spelling review remains red, although this change introduces no missing keys, placeholder failures or unreadable sources and its new guarded keys exist in all four locales. No uninterrupted full-repository pytest pass is claimed: covering owner tests, real native cases and earlier Step evidence establish this cleanup's scope. Host-dependent os_keychain tests still require an interactive desktop logon; the available native fixtures preserve that limit rather than bypassing it. Independent sign-in, desktop and manager plans remain open under their owners.

Verdict: PASS for the reviewed implemented working-tree cleanup. No critical or high product finding remains. Required covering behavior, exact reachability and export gates, duplication remeasurement, style, format, configured types and import boundaries have applicable passing evidence. The remaining advisory token matches remain visible with the source review above.


### october-shared-checkpoint | low | Four tested receipt edits remain with the concurrent sign-in working changes

The receipt owner, finite receipt_binding_probe fixture, binding unit tests and human-login receipt integration tests share the active application-sign-in P01.S05 implementation. The fixture delegates that workstream's actual production binding-refusal kernel, which is not yet in HEAD. Saving an older owned capture would omit the kernel or overwrite the current proof-only readers. Those four tested working edits are deliberately retained together; the independent S07 checkpoint excludes them and preserves the shared index. The implementation and passing review apply to the working tree including these files, not to a claim that the independent commit alone reproduces the complete current receipt tree. Their current paths remain recorded in the ledger so the mixed ownership is explicit.

## Recommendations

Make export finding identities relative to the scan root under both production and
isolated detector-teeth execution, then rerun the focused three-file suite and the live
export gate. Recompute the filtered audit outcome from the filtered populations so an
empty exact projection is clean while a non-empty exact projection still fails. Resolve
all strict checker diagnostics without suppressions, aliases, shims, or widened
exclusions. Rerun the exact audit, all three zero-target gates, their detector-teeth
suite, Ruff, and the repository's owning strict type gate before declaring closure.

These recommendations have been satisfied in the re-reviewed tree. No follow-up
implementation recommendation remains from this audit.
