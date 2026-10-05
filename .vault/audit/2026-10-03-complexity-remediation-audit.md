---
tags:
  - '#audit'
  - '#complexity-remediation'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:710b682784188705776cb71df0d6ddfb62eec1f11f6fa9a59fbf165598206fba'
related:
  - "[[2026-10-02-complexity-remediation-plan]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-09-11-justfile-design-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-04-tui-architecture-authenticated-tui-visibility-adr]]"
---

# `complexity-remediation` audit: `Integrated complexity remediation review`

## Scope

Review the behavior-preserving production refactors in the approved L1 plan, including the recorded S01-S11 work and their direct consumer migrations. Target is the live, uncommitted filesystem in `Y:/code/cadrumo-worktrees/tui`; concurrent edits continued throughout execution. Exact pre-edit source captures, owning test receipts and the execution ledger establish the available comparison evidence. A Git tracked-file list was not used to enumerate acceptance scope. The configured production roots remain `src/cadrumo`, `src/cadrumo_harness`, `dev` and `packaging`.

The accepted import-centralization decision requires actual canonical defining owners, direct consumers and no compatibility re-export facades. The accepted justfile decision preserves advisory exit semantics. The TUI decisions govern operation-envelope and authenticated visibility behavior. Integrated review traced schema bindings, request custody, receipt/result projection, writer and cancellation fences, runtime cleanup and registry parser/materialisation handoffs. No commit, staging, financial-authority publication or external deployment was requested or performed.

The user's complexity-count requirement is achieved: the completed official four-root `just audit-complexity` run reports **0 current hotspots**, exit 0, at `.logs/audit-runs/2026-10-03/20261003T115300.844754Z-audit-complexity-77960-c3f20c18/run.log` (finished 2026-10-03T11:55:11.690201Z). Detector semantics and population remain unchanged. The post-run filesystem freshness check also reports zero for the one production source modified during or after this interval. The production registry builds, and the fresh native comparison suite passes 49 tests. Integrated review verdict: **PENDING** because required broader authority, native-matrix and type verification remains unresolved. No confirmed high or critical regression was found in the reviewed workflows. Historical checkpoint findings remain below alongside subsequent recovery evidence.

## Findings

### verification-coverage | medium | Owning passes do not establish a clean integrated suite

Applicable passing evidence includes the final 50-test live read/filed-history suite at `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T105352.561109Z-pytest-53284-f71157c3/run.log`, the 85-test final work-review/filing-import/review-package/reconciliation cohort at `20261003T102651.801809Z-pytest-47768-121d3a86`, exact validation and serialization schema parity for 13 Modelo contracts in `.logs/complexity/final-modelo-schema-parity.json`, the 34-test signed-composite grammar/codec suite at `20261003T105958.533474Z-pytest-27448-e7cfe6a8`, and the 37-test note-literal/provenance/PDF suite at `20261003T110303.480691Z-pytest-67812-761abf56`. The latter explicitly excludes three whole-corpus/authority cases that previously failed or timed out; it does not cover those cases. The ledger retains the commands, scope and additional owning receipts; overlapping suites must not be summed into a unique total.

The seven-source registry integration cohort finished without timeout with 422 passed and 21 failed at `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T102853.832580Z-pytest-70340-381e8933/run.log`. Failures concern M353 source selection, missing M232 variable-envelope authority, inline-binding spans/refusals, stale M720 layout state, M347 legal-reference sequence order and M200/303/220 workbook geometry/shape contracts. Earlier broad tree-validator and source-provenance/PDF runs also retain failures or timeouts in the ledger. Exact original-versus-current execution over the same live authority inputs was not established for those failures. They remain unclassified; they cannot be called unchanged baseline failures or suppressed as unrelated merely because owning unit tests pass.

### current-input-admission | medium | Concurrent authoring blocks fresh collection and editable builds

The final combined render-profile owning command stopped in collection with the current M347 `2011-2024` edition resolving export fields to undeclared `decl.importe-total-anual` and `decl.total-personas-entidades`; see `20261003T105341.482242Z-pytest-67572-d5549391`. A normal editable UV build encountered the same authority validator. Checks used `uv run --no-sync` with the existing installed runtime; no validator or registry data was relaxed to manufacture a passing build.

A final comparison-suite repeat stopped before its test bodies at the concurrently added `ForeignAssetRecordJoinRefusedError` lacking an ErrorCode registry declaration; see `20261003T110040.420177Z-pytest-48200-3d60f6bd`. The earlier read-only composition probe built 272 definitions, 272 registrations and 272 public contracts, with canonical schema bindings, projectors and access resolvers, and validated current runtime status/transport imports. That probe predates this later import blockage and does not prove the newest composition graph loads.

### native-matrix-coverage | medium | Six touched M036 and audit operations lack marker scenarios

The current registered matrix has no `_EXPECTATIONS` cases for `modelo.036.read`, `modelo.036.query`, `modelo.036.record`, `modelo.audit.read`, `modelo.audit.query` and `modelo.audit.export`. Its prior exact marker selection produced six passes and six failures at `case is None`. These operations and the missing-case refusal branch also exist in the historical source inspected during review; the refactor did not author new expectations. The scenarios are nevertheless applicable to touched access/builders and remain an acceptance gap. Behavior-grounded fixtures are required before claiming native matrix coverage; expected payloads must not be copied from failing output or invented.

The isolated native profile-guard recovery gap is resolved: `src/cadrumo/entrypoints/cli/tests/test_profile_guard_action_recovery.py` passes in `20261003T104933.063023Z-pytest-63140-b0264f4a`. The fixture explicitly creates its isolated storage root, starts/stops the existing native runtime server and supplies bounded explicit profile password proofs. It retains denial/action, retry and persisted-state assertions and checks the canonical process-scoped session warning. Production authorization and session guards were not weakened. Other platform, private-corpus and native prerequisite gaps remain as individually recorded in the ledger.

### static-check-coverage | medium | Whole type cleanliness is not proved by focused passes

Final reviewed owners have focused Ruff/format/ty and, where applicable, BasedPyright passing evidence. Retained private-owner import diagnostics in registry sources, untyped JSON/path diagnostics in the sequence runner and existing workbook annotations remain visible in the ledger. Original source captures support those local comparisons but do not establish a passing original whole-type run. The previous `just check-types --count` reported 147 findings; count mode exit 0 is not a type-check pass. A fresh aggregate check is root-owned. No suppression was added to silence a diagnostic.

### error-detail-capture-policy | low | Capture opt-out preserves historical receipt disclosure semantics

`application/operations/operation_definition.py` documents `public_error_detail` as whether bounded detail is recorded. `_supervisor_execution._stored_error_detail` applies the opt-in before encrypted operand storage. The resolver in `error_detail.py` retains terminal condition/revision, exact definition digest, fixed schema and referenced encrypted operand checks; `entrypoints/runtime/operation_host.py` applies current `AccessAction.RESULT` authorization before releasing the result. The capture flag is not part of the public digest and is not rechecked for historical reads. Pre-refactor source comparisons and the extracted checks show that recording, digest and read behavior were preserved. Disabling future capture is therefore not revocation of already recorded detail. No privacy-policy migration is warranted by this behavior-preserving refactor. Any future revocation requirement must explicitly decide the historical receipt and public contract semantics.

### canonical-parser-enrollment | low | Canonical grammar owners retain active detector coverage

Six regulatory-prose census entries were migrated from retired former homes to the actual current defining parsers in `dev/registry/analysis/regulatory_prose_parser_channel.toml`; exact stale former-owner entries were removed. The final census, derived largest-parser check and representative withheld-enrollment defect all pass at `20261003T104144.337490Z-pytest-5668-322d3b39`. Parser authority reasons and detector population/thresholds were not loosened. The final signed-composite extraction preserves width-nature/duplicate/nature refusal before anchor-width refusal and preserves remaining grammar/geometry/codec order.

### aggregate-type-check | medium | Fresh count reports 142 type findings

The completed `just check-types --count` repeat reports 142 current findings, compared with 147 at the previous checkpoint. The wrapper returned exit 0 because it was run in count mode; this is a failed clean-type requirement, not a passing type gate. It does not establish baseline classification for all diagnostics. Local overview owner Ruff/format/ty/Based checks now pass without suppression.

### complete-complexity-scan | low | Completed four-root scan reports zero current hotspots

The official `just audit-complexity` command completed with exit 0 and **0 current hotspots** across `src/cadrumo`, `src/cadrumo_harness`, `dev` and `packaging`. Receipt: `.logs/audit-runs/2026-10-03/20261003T111510.709092Z-audit-complexity-61152-ac2490ea/run.log` and `run.json`; interval 2026-10-03T11:15:10.709092Z through 11:17:58.307302Z. CC/MI/cognitive detector semantics, source inclusion policy and thresholds remain unchanged. All owned production writes had stopped before this run. The requested zero-complexity inventory is achieved for this completed live-tree interval. Integrated verdict remains **PENDING** for the unresolved applicable verification findings above; zero complexity is not a whole-QA passing claim.

The final overview stages pass exact owner Ruff/format/ty/Based checks; their owning suites pass 20 explanation and 94 calendar cases (`20261003T111155.035863Z-pytest-26488-dcdaaa55`, `20261003T111106.279935Z-pytest-62968-8ec4a00c`). Current declaration absence/empty values, exclusion order, flattened facts and applicability-evidence warning behavior were preserved. The final domain applicability extraction passes exact-owner static checks and 34 current applicability/cross-surface tests (`20261003T111539.368643Z-pytest-41384-322729c9`); direct derived-evidence branch coverage is being completed separately without production edits.

### comparison-collection-recovery | low | Current composition and native comparison suite pass

After the concurrent foreign-assets error-code declaration landed, `build_production_operation_registry()` built successfully on the current graph. The fresh all-marker `dev/docs/sequences/tests/test_compare.py` suite passed 49 tests with exit 0 at `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T111618.009997Z-pytest-25552-dc838fa9/run.log`. It exercises real native CLI golden generation/round-trip, authored-only sandbox normalization and representative corrupt/extra-key/pre-tokenized output defects. The comparison collection gap recorded at the earlier checkpoint is resolved for this current run. Broader authority admission, native matrix and type findings are not thereby resolved.

### ledger-evidence-branch-coverage | low | Direct derived-evidence and exclusion-order checks pass

The direct branch gap in the final applicability extraction is resolved. `src/cadrumo/domain/calculations/registry/tests/test_applicability_canonical.py` now uses hydrated production M720/M136/M347 rules and typed profiles to check derived yes with declared no/unanswered, derived no with declared yes/unanswered, unknown/missing derivation, period-companion independence, a holding legal exclusion after an undetermined finding and first-undetermined authored order. The latter checks both original and reversed actual exclusions against their independently evaluated typed findings, with a positively declared required fact, so it tests aggregation order rather than copying a failing result.

Final owning run: 9 passed, exit 0, `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T112810.327975Z-pytest-30652-b1bcfd62/run.log`. Exact-test Ruff check, Ruff format check, ty and BasedPyright also pass. The initial fixture expectation confused generated INCOMPLETE rationale with the configured legal reason; the test was corrected against the actual typed exclusion contract without changing production. The remediation made no further production edits after the completed zero scan. The integrated review remains **PENDING** for the broader unresolved authority, native-matrix and type findings, while the requested complexity-count goal has a completed zero receipt.

### concurrent-input-final-review | low | Later concurrent hotspots cleared and fresh full gate remains zero

Later filesystem freshness checks identified newly added CC16 threshold-advisory, CC11 exclusion-advisory and CC11 overview registration-validation hotspots. They were cleared within the existing contracts, without detector, authority-data or refusal-policy changes. Final owner Ruff/format/ty/Based checks pass. The latest overview owning suite passes 20 tests at `20261003T115200.649188Z-pytest-23188-814c54ac`, retaining filing-year profile/ledger evidence and refusal order.

The final official `just audit-complexity` command completed with **0 current hotspots** over all four configured production roots, exit 0; receipt `.logs/audit-runs/2026-10-03/20261003T115300.844754Z-audit-complexity-77960-c3f20c18/run.log` and `run.json`. The post-run filesystem census found one source modified during or after this scan (`src/cadrumo/application/invoices/source_resolver.py`); its latest exact-file CC/MI/cognitive measurement is also **0**. This supplements the complete run for the current concurrent source, without changing population or thresholds.

Focused threshold tests produced 1 pass/2 failures (`20261003T113700.812834Z-pytest-37340-3c2c4ba9`), and exclusion tests produced 2 passes/1 failure (`20261003T114606.467510Z-pytest-21776-f9c7bc75`). The isolated captured-original/current parity probe passes at `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T115343.390004Z-pytest-83136-dd2fa3cd/run.log`, using actual fixture invoices and the same current pinned authority with copied globals and AST-loaded functions, without production module patching or shared source replacement. D has count1 and no threshold advisory on both versions. E2024 has count0 in direct binding calculation before diagnostics; E2025 has count1; both advisory tuples match exactly. The export-assimilated fixture has claveB/categoryNone and no exclusion advisory on either version. These expectations therefore fail unchanged by the extractions on the measured inputs; their authority/classification causes remain with the input owner. The replay is `.logs/complexity/test_source_resolver_captured_parity.py`.

Final integrated verdict remains **PENDING** for the unresolved broader authority/native matrix/type evidence already recorded. The requested production complexity inventory is **zero** at the latest complete run and freshness check. No high/critical refactor regression was confirmed, no financial data or guard was relaxed, and no commit/staging/publication was performed.

## Recommendations

The official four-root zero-count requirement is met by the completed receipt above. Keep S05 and any Step with unresolved applicable verification open; a passing complexity inventory does not establish a passing integrated review. Preserve the scope and thresholds for future source changes.

For the broader integrated review, reconcile each failed authority or parser invariant with the current input owner, then rerun the smallest affected boundary with exact inputs or establish original/current parity in an isolated fixture. Preserve admission/refusal policy, financial authority, sequence order, runtime and credential guards while doing so. The current composition and comparison recovery receipts are passing; repeat those checks only when relevant source or input changes invalidate them. Supply the six missing native marker scenarios from supported operation behavior. Resolve or classify the aggregate type diagnostics with exact comparison evidence. These requirements remain verification work; this audit does not authorize rewriting financial authority or publishing externally.
