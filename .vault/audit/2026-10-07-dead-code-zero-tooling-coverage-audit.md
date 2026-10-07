---
tags:
  - '#audit'
  - '#dead-code-zero'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:1e45ce971695eac56e6104afe958dbf0aa3ad45173adea56f3d01834c63d4d7c'
related:
  - '[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]'
  - '[[2026-10-07-dead-code-zero-plan]]'
---
# `dead-code-zero` audit: `Dead-code audit and native build scope`

## Scope

User request: run every dead-code audit and verify coverage or exclusion of the recent build tools, CMake, Rust and binaries. Read-only product inspection plus routine fixes to the existing audit tooling; no new architectural commitment or implementation plan was needed. Evidence describes the concurrent worktree inspected on 2026-10-07, not an immutable all-green checkpoint.

Vulture measures Python under `src/cadrumo` plus `dev/audit/vulture_whitelist.py`, at the configured 80% confidence floor. `dev/`, `packaging/`, `native/`, CMake inputs, Rust/C/frontend code, generated build outputs and compiled binaries are outside this instrument's subject. The shipped-code reachability audit uses wheel inclusion policy, declared console scripts and module execution roots, and consults the harness plus dev/tests as consumers. It does not analyze native-language execution or establish Rust/CMake cleanliness. Semantic code discovery was unavailable: the RAG server could not start because another process owned the machine GPU. Vault search, the complete ADR listing and targeted source reads supplied discovery.

Follow-up removal, wiring verification and analyzer repair are authorized by `2026-10-07-dead-code-zero-plan`; the appended findings record its S01-S03 closure.

## Findings

### coverage-population | high | Excluded modules could satisfy the scan population floor

Resolved. `dev/audit/dead_code.py:224` now reads Vulture's effective configuration and counts files after its case-insensitive absolute-path exclusions. Previously the separate production classifier counted files Vulture could exclude, allowing an intact but wholly excluded tree to satisfy the floor. An over-broad exclusion now produces an unavailable scan before launch. Invalid Vulture configuration also produces the typed unavailable outcome. Existing partial-parse and unreadable-module refusal remains intact.

### checkout-location | medium | Broad exclusions could discard production files below a test-named parent

Resolved. The previous `*test_*.py` and `*/tests/*` patterns matched absolute checkout-location segments. `pyproject.toml:1317` now anchors exclusions under `src/cadrumo` on Windows and POSIX, and explicitly excludes bundled data and conftest files. A real Vulture subprocess under pytest's test-named scratch path detects the planted product dead import while ignoring test/data modules and out-of-scope native/build files. Its selected population agrees with the runner's denominator.

### scope-disclosure | medium | Product-only Python results did not disclose native and build limits

Resolved. `dev/audit/dead_code.py:208` declares the included root, whitelist support file and excluded roots/surfaces. Console and JSON reports expose these limits; `dev/audit/dead_weight.py:101` carries the same scope in the normalized dead-weight summary and persisted signal artifact. Build tooling, CMake, Rust/C/frontend sources and compiled artifacts are deliberately excluded rather than silently treated as audited.

### current-product-findings | medium | The inspected product still has static reachability findings

Vulture: 2 findings across 3,278 offered modules, both at 100% reported confidence. They are required parameter names on `SpreadsheetVerifyPort.__call__` (`src/cadrumo/application/modelo/modelo_spreadsheet_operation_contracts.py:337`, `before_mutation`) and `DiagnosticFormatter.formatTime` (`src/cadrumo/core/diagnostic_log.py:142`, `datefmt`). Their protocol/override signatures explain the unused parameter; neither establishes dead behavior. They remain visible without broadening the global whitelist.

Shipped reachability: 3,266 of 3,277 modules runtime-reachable; 11 unreachable modules; 36 exact unused-symbol candidates, 7 name-match candidates and 15 name-match-data candidates; 1 orphaned test module. The export-consumption gate reports 13 unconsumed exported names. These sets overlap and must not be summed into a defect total. Complete locations are in `.logs/dead-code-reachability-2026-10-07.json`; candidates require caller and feature-ownership review before deletion.

The combined dead-weight run additionally reports 47 duplication clusters over 3,143 files: 9 executable or unclassified, 13 declaration-only and 25 import-only/overlapping, at 0.10% duplicated lines. Its native run log and signal artifact are under `var/storage/development/.logs/test-runs/2026-10-07/20261007T070925.056872Z-audit-dead-weight-61308-77f6df66/`.

### verification-limits | medium | Repository-wide checks do not establish an all-green worktree

The focused Python audit, integration, advisory and first-party-source tests passed: 64 tests, with both unit and integration markers selected. Evidence: `var/storage/development/.logs/test-runs/2026-10-07/20261007T071535.892961Z-pytest-61484-ada9757e/run.json`. Focused Ruff checks and formatting pass; the edited TOML passes its owning data-format checker.

Repository-wide style reported 3 import-order errors outside the changed audit files; formatting reported 5 files outside those files. The configured type runner reported 66 diagnostics; its report is `.logs/dead-code-types-2026-10-07.txt`. The import-boundary run was unavailable/failed: its dev import-load target metadata was stale and the governed source changed during execution; it also reported 14 hard findings. Its report is `var/storage/development/.logs/test-runs/2026-10-07/20261007T071137.443208Z-check-import-boundaries-34208-da2ee866/artifacts/import-health.json`. These observations are outside the bounded audit-tool repair and are not represented as a passing repository checkpoint.

### rerun-baseline | medium | The follow-up rerun exposed twenty remaining candidate declarations

Resolved under the approved `2026-10-07-dead-code-zero-plan`. The fresh baseline already had all 3,264 shipped modules reachable, zero exact findings and zero orphan tests, but twenty weaker symbol candidates and one Vulture finding remained. Evidence: `.logs/dead-code-rerun-reachability-2026-10-07.json` and `.logs/dead-code-rerun-vulture-2026-10-07.json`. The earlier eleven-module population above is historical; the rerun measures the tree after the preceding removals and wiring.

### unused-product-declarations | low | Sixteen unused declarations were removed

S01 removes three unused custody protocol methods and their three persistence wrappers, the receipt-type probe and its wrapper, two unused pointer transitions, the unused hosted-profile count, broad managed-artifact child inventory, the obsolete row-set-header result field, two unused Google condition members and the undeclared remote-handle transport value. The live filesystem custody kernels, locking and revision checks, explicit login, runtime idle fencing and targeted publication reconciliation remain exercised. Owning tests use supported operations instead of keeping test-only product APIs alive. The retired receipt-resume fake and its unused local-record fixture were removed with their callers. Source and tests are committed in `933e276c96`.

### actual-consumers | low | Four legitimate candidates were retained through structural analysis

S02 resolves `DiagnosticFormatter.formatTime` through the installed logging base contract, `StoragePathRules.enforce_existing_permissions` through the native generator's qualified `_asdict()` read, `InheritedEnvironmentValueKind.OPAQUE` through actual whole-enum iteration, and `GoogleSavedReviewScreen.reject_pending_prepublication` through the installed acceptance runner's typed screen collection and exception-handler cleanup. The mandatory `datefmt` keyword is preserved and explicitly discarded because diagnostic timestamps use UTC ISO format. Real-source controls cover the formatter, generator and acceptance cleanup. Shadowed names, unrelated methods, unknown receivers and mere record construction retain findings. Final review additionally removes generic argument-based enum clearing: passing an enum to `print()` is not a member read. No suppression, fake caller or feature-name inventory was added. S02 is committed in `82bd056ea5`; the conservative enum correction belongs to S03.

### registered-schema-consumers | low | Schema validation consumes the three cascading response-version fields

A concurrent registry refactor exposed `GoogleReviewResponse.response_version`, `CensalReviewResponse.response_version` and `GoogleConsentResponse.response_version`. They participate in real registered response schemas. S03 follows the typed model payload passed to `cls.model_validate`, the registered Pydantic validator's `ValidationInfo.data` lookup, and its proven schema-generation sink. Metadata fields that are merely printed and rebound or shadowed values do not qualify. The real registry and response declarations form the positive control. The existing wrap validator also now types its handler and return as `Self`, preserving subclass identity and eliminating the configured Pyrefly error without a runtime change.

### reporting-integrity | low | Clean scans retain the verified-reference census

The scan formerly discarded `data_cleared` and `dev_cleared` when constructing a clean result. S03 carries both computed counts through the clean constructor. The final scan records 193 shipped-data clearances and 87 resolved development-reference clearances alongside zero findings. These are existing verified consumers, not added allowances or a defect count. Regression coverage checks the complete clean outcome and census; the actual native-generator control remains passing.

### measured-zero | low | Every measured dead-code population is empty

The final stable-source scan reports:

| Signal | Fresh rerun | Final |
| --- | ---: | ---: |
| Runtime-reachable shipped modules | 3,264 / 3,264 | 3,264 / 3,264 |
| Unreachable modules | 0 | 0 |
| Type-only / module-execution-only modules | 0 / 0 | 0 / 0 |
| Exact unused-symbol findings | 0 | 0 |
| Heuristic symbol candidates | 20 | 0 |
| Orphan tests | 0 | 0 |
| Vulture findings | 1 | 0 |

Export consumption also reports zero findings. The three configured reachability, symbol and export predicates consume one complete typed scan; the export predicate still parses the live exports and production imports. Evidence: `.logs/dead-code-zero-reachability-final-stable.json`, `.logs/dead-code-zero-gate-verdicts-final-stable.json` and `.logs/dead-code-zero-measurement-final-stable.log`. A full scan of the concurrent worktree also reached zero before the final conservative enum/census corrections: `.logs/dead-code-zero-reachability-closure.json`.

The freshly rerun native `audit-dead-weight` command reports zero Vulture findings across 3,265 offered modules, including its whitelist support file. Its separate duplication dimension has 48 clusters over 3,133 files at 0.10% duplicated lines: 10 executable or unclassified, 13 declaration-only and 25 import-only or overlapping. Duplication is a separate advisory population. Evidence: `.logs/dead-code-zero-dead-weight-final.log` and the native run `20261007T104334.417987Z-audit-dead-weight-62992-00924a2e` under `var/storage/development/.logs/test-runs/2026-10-07/`.

Native Rust, C, CMake, frontend sources, build outputs and binaries retain the explicit scope exclusions described above. Python consumers of generated native contracts now receive accurate structural treatment; no native-language cleanliness claim follows from these results.

### final-integrated-review | low | S01-S03 pass against the recorded owned patch

PASS. Review covers the product removals in `933e276c96`, consumer repairs in `82bd056ea5` and the final S03 working patch, including CLI/TUI saved-review consent, rejection, exact revision binding and publication enrollment. The quality-gate product-boundary, reachability burndown and Google outbound review ADRs govern this scope. No high or critical findings remain. Current semantic discovery could not start because local-settings Git protection could not be verified; accepted ADR reads, feature status, targeted source and complete changed-code review supplied grounding. The earlier GPU failure above remains its original historical observation.

All twelve configured quality gates have applicable passing evidence. Seven unchanged native suite commands pass in `.logs/dead-code-zero-configured-stable-snapshot.log`; the configured ty, Pyrefly and BasedPyright sweep passes across Linux, Windows and macOS analysis targets in `.logs/dead-code-zero-types-stable-snapshot.log`. Final source/import authority passes in `.logs/dead-code-zero-import-final-stable.log`: all fifteen contracts kept, all 4,515 configured modules loaded, zero hard findings, zero architectural debt and authoritative stable source. The three dead-code/export predicates pass in the final measurement artifacts above. Scoped Ruff lint/format and ty checks pass for the final analyzer corrections; unchanged dependency, persistence, secure-store and docstring evidence remains applicable.

The final focused snapshot run passes all 104 analyzer, schema-binding, CLI and TUI cases with both unit and integration markers selected: `.logs/dead-code-zero-tests-stable-snapshot.log`. S01 owning persistence, runtime and Google verification passes 88 cases after corrective reruns, with two OS-keychain cases skipped because this Windows host cannot access the required credential store. S02's analyzer, formatter and rotation coverage passes 156 distinct cases after corrective reruns. The census extension passes 73 distinct focused cases after correcting its expected total and rerunning the four record cases; evidence is `.logs/dead-code-zero-final-counter-tests.log` and `.logs/dead-code-zero-final-counter-retry.log`. Overlapping test sets are not summed.

Shared-tree import attempts correctly refused source changes during concurrent execution; one attempt additionally saw a temporary missing import in another task's test, subsequently corrected by its owner. Validation therefore used a detached checkout of committed baseline `f0be8532f5fdd44c601cd60a2747436a6f3e9c7b` plus exactly ten owned source/inventory files. Every configured command and population was preserved. `.logs/dead-code-zero-validation-snapshot.json` records every file's SHA-256 and patch SHA-256 `5767e50f0d29982fd9dd524dd4532a2803ed68a47270205780a5ca60779f349b`; all ten files matched the main worktree after verification. These passing results cover the owned patch against that baseline; the shared worktree continues to contain other tasks' changes.

## Recommendations

The measured dead-code populations are resolved. Keep the real-consumer regression controls and explicit native/build scope disclosure. Investigate duplication separately if requested. If native dead-code analysis is desired, use authoritative language/build tools and report target/platform coverage separately.
