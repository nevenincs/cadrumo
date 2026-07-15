---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# `cli-authority-verb-conformance` audit: `Wave W01 atomic Step reviews`

## Scope

Reviewed commit `36ff8f1850bac3f0335c78f73ab8499f3bbda035` against the accepted import-linter prerequisite in the ADR, the implementation grounding in the research and reference, plan Step `W01.P01.S01`, and its Step Record. The review covered safety, exact intent, tracked root-authority uniqueness, compatibility behavior, and attribution of every immediately observable remaining contract failure.

The review was grounded with `vaultspec-rag search "import-linter root package cadrumo architecture contracts" --type code`, then confirmed with commit-scoped `git show`, `git grep`, `git ls-tree`, package-tree probes, targeted `rg`, and fresh uncached import-linter runs.

## Findings

S01 has no actionable finding. Verdict: **PASS**. No CRITICAL, HIGH, MEDIUM, or LOW issue was identified, and S02 is not blocked.

The commit changes only `.importlinter:2` from the nonexistent `aeat` package root to the real `cadrumo` package root and adds its Step Record. The commit tree contains `src/cadrumo/__init__.py`, contains no `src/aeat/__init__.py`, and contains exactly one tracked `.importlinter`. Packaging-smoke copies under `var` are ignored generated artifacts, not alternate authorities. The change adds no alias, fallback, compatibility parser, or second declaration.

An uncached review run constructed the live 3,421-file graph. The focused registry, domain-to-application, and domain-to-adapters contracts remained kept; the core contract reported only the helper-mediated path from `cadrumo.core.tests.test_isolation_fixture_state_root_coverage` through `cadrumo.tests.secure_sql`. The complete contract run stopped on the two expected unmatched entries for `cadrumo.application.live._censo` and `cadrumo.application.user_profile._censo_sync`. At the reviewed commit, the first source module is absent and the second has no adapter import, so those entries are correctly assigned to S02 and S03; the exact test-helper route is correctly assigned to S04.

The shared worktree advanced after the S01 commit and carried peer-owned source edits during review, so the current dependency count was 16,152 rather than the executor-time 16,153 recorded for S01. The package-root behavior, file count, contract verdicts, and failure attribution remained unchanged; this is worktree-context drift, not an S01 defect.

S06 has no actionable finding. Verdict: **PASS**. No CRITICAL, HIGH, MEDIUM, or LOW issue was identified, and S07 is not blocked.

Commit `2a1eb45b1b0bcd72eba3ef8a9a5f2deb0137e2db` removes only the concrete `TransactionCatalogueRepository` adapter import and the optional ambient-construction branch from `aggregate_irnr_income_ledger_from_repositories`, makes `TransactionCatalogueRepositoryProtocol` required, preserves the bucket-identity guard and aggregation behavior, and adds the S06 Step Record. The resulting module imports inward through core and domain ports and contains no concrete adapter reference, fallback, alias, compatibility default, or second IRNR repository constructor.

The review was grounded with `vaultspec-rag search "IRNR income ledger injected transaction repository remove ambient fallback" --type code`. Exact commit-scoped caller enumeration found one production call in `LedgerIrnrIncomeAggregationSourceResolver` and two direct real-repository test calls; all three pass the repository argument. Structural substitutability is intact: both the concrete encrypted repository and the source mesh's `_MemoizedTransactionCatalogueRepository` implement the Protocol members consumed by the function (`bucket_id`, `load`, and `partition_by_date_range`). Focused Ruff passed, and the real encrypted-repository M210 suite passed two tests.

The only remaining IRNR composition door is the top-level-exported `LedgerIrnrIncomeAggregationSourceResolver` constructor, which still accepts `TransactionCatalogueRepositoryProtocol | None` and can forward `None` in ledger mode. Exact construction search found one production construction, and it already injects the source mesh's shared memoized repository; no alternate production construction or duplicate M210 aggregator exists. S07 therefore owns the complete remaining public-constructor hardening. Optional repository construction in other ledger families is not substitutable with the selected-code M210 IRNR authority and is outside this accepted defect's scope.

S09 has no actionable finding. Verdict: **PASS**. No CRITICAL, HIGH, MEDIUM, or LOW issue was identified, and S10 is not blocked.

Commit `5695c6a0335ce7f63d5827c2ee56fc63b907e8a4` changes only the concrete invoice-repository import, four invoice-repository annotations, the directly affected public-argument documentation, and the S09 Step Record. Exact commit review found no changed condition, call, assignment, construction, exception path, or persistence behavior. The current verification module contains no `InvoiceCatalogueRepository(...)` construction, concrete invoice-repository annotation, or import from `adapters.persistence.profile.invoices`; every verification boundary now names the public `InvoiceCatalogueRepositoryProtocol` port.

The review was grounded with `vaultspec-rag search "modelo verification invoice repository protocol OSS IOSS resolver" --type code`, which returned the legacy Modelo 369 resolver call and all four Protocol-typed boundaries. Exact caller and symbol searches confirmed that verification only forwards the injected value through its finding collectors into `OssIossLedgerSourceResolver`. The runtime-checkable public Protocol declares `bucket_id`, `exists`, `load`, and `save`, and the concrete encrypted `InvoiceCatalogueRepository` implements those same members with compatible signatures, so existing concrete callers remain structurally valid without runtime coercion or a compatibility wrapper. Focused Ruff passed, and the real encrypted-storage dormant Modelo 369 suite passed five tests.

The only retained OSS/IOSS concrete composition edge is `oss_ioss_candidates_from_repositories` in `src/cadrumo/application/aggregation/_oss_ioss.py`, where one fallback constructs `InvoiceCatalogueRepository` when no repository is injected. Its helper, aggregate wrapper, and resolver constructor still carry concrete annotations but converge on that single fallback; production calculation and legacy verification both feed the same resolver path. S10 therefore owns the complete receiving-annotation widening while deliberately retaining that sole default construction authority.

S02 has no actionable finding. Verdict: **PASS**. No CRITICAL, HIGH, MEDIUM, or LOW issue was identified, and S03 is not blocked.

Commit `69469505fe45ae786c01f7bcf0a9a8ae4b711ca3` removes exactly the single `cadrumo.application.live._censo -> cadrumo.adapters.**` layered-contract waiver and adds only the S02 Step Record, its plan closure, and regenerated feature-index links. The `.importlinter` diff changes no contract declaration, wildcard, neighboring ignore, root package, or `unmatched_ignore_imports_alerting = error` setting. Commit-scoped tree and symbol searches found no tracked `src/cadrumo/application/live/_censo.py`, import edge, lazy registration, `import_module`, `__import__`, or `find_spec` caller. The Spanish-stem rule example and UTF-8 debt-ratchet string naming the absent path are declarative text, not runtime or import-graph consumers.

The review was grounded with `vaultspec-rag search "stale live censo import-linter ignore no source module" --type code`, followed by commit-scoped `git show`, `git grep`, `git ls-tree`, `git ls-files`, `fd`, and targeted `rg`. A fresh full uncached import-linter invocation no longer reports the removed S02 waiver and stops only on the unmatched `cadrumo.application.user_profile._censo_sync -> cadrumo.adapters.**` entry owned by S03. A focused uncached four-contract run analyzed 3,421 files and 16,152 dependencies: the registry and both domain contracts were kept, while the core contract was broken only by `core.tests.test_isolation_fixture_state_root_coverage -> tests.secure_sql -> adapters`, the exact helper-mediated route owned by S04.

## Recommendations

Proceed to S02 with the atomic gate intact: remove only the stale live-censo ignore, preserve the corrected `cadrumo` root, and do not weaken unmatched-ignore alerting or any contract. S03 must remove the separate censo-sync ignore, and S04 must add only the exact test-to-helper route in the reporting core contract. Keep later Waves blocked until W01 reaches the planned uncached five-contract pass and non-vacuous `199/78/2` ratchet proof.

Proceed to S07 and make `LedgerIrnrIncomeAggregationSourceResolver` require `TransactionCatalogueRepositoryProtocol` without introducing a default, late constructor, or compatibility path. Retain the sole production composition through `_resolve_bucket_source_mesh` and its memoized repository; S08 must then prove the complete M210 path against the real encrypted repository.

Proceed to S10: widen the three OSS/IOSS receiving annotations and their documentation to `InvoiceCatalogueRepositoryProtocol`, retain exactly the existing `InvoiceCatalogueRepository(bucket_id=bucket_id)` fallback in `oss_ioss_candidates_from_repositories`, and add no second constructor, ignore, alias, or compatibility path.
