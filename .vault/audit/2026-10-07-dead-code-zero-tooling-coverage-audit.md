---
tags:
  - '#audit'
  - '#dead-code-zero'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:cb0cff0ba648309ab60637926fbc2c7ef2c6134adc8670aee0bad33330f7b213'
related:
  - "[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]"
---
# `dead-code-zero` audit: `Dead-code audit and native build scope`

## Scope

User request: run every dead-code audit and verify coverage or exclusion of the recent build tools, CMake, Rust and binaries. Read-only product inspection plus routine fixes to the existing audit tooling; no new architectural commitment or implementation plan was needed. Evidence describes the concurrent worktree inspected on 2026-10-07, not an immutable all-green checkpoint.

Vulture measures Python under `src/cadrumo` plus `dev/audit/vulture_whitelist.py`, at the configured 80% confidence floor. `dev/`, `packaging/`, `native/`, CMake inputs, Rust/C/frontend code, generated build outputs and compiled binaries are outside this instrument's subject. The shipped-code reachability audit uses wheel inclusion policy, declared console scripts and module execution roots, and consults the harness plus dev/tests as consumers. It does not analyze native-language execution or establish Rust/CMake cleanliness. Semantic code discovery was unavailable: the RAG server could not start because another process owned the machine GPU. Vault search, the complete ADR listing and targeted source reads supplied discovery.

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

## Recommendations

Review the remaining product candidates under their current feature owners, especially the Google spreadsheet, review-publication and profile-authentication surfaces. If native dead-code analysis is desired, use the authoritative language/build tooling for that subject and report its target/platform coverage separately. The current request's permitted exclusion option is implemented and visible.
