---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:2e033984d42e61b6a0a211bf91dfe8749bb1e05a4a765a6b5f502b0f442a83c3'
related:
  - "[[2026-09-15-runtime-verification-lane01-r02-revision-view-repair-audit]]"
---

# `runtime-verification` audit: `lane01-r03 view contract closure`

## Scope

Session `lane01-r03-view-contract-closure`, a continuation of the linked lane01-r02 revision-view repair audit. It had three authorized tasks. First, correct the `revisions` column of `aeat app modelo list`. Second, settle what C13's indexed-snapshot test actually covers. Third, check that the private view-validation scope holds when a view is nested or revalidated. Commit, push, authority rebuild and publication were not authorized, and none happened.

Checkout: worktree `Y:/code/cadrumo-worktrees/main`, branch `main`, HEAD `eedac16053`. The lane01-r02 production and test changes were already committed at HEAD by the worktree's sync auto-commits, so this session started from them. The two files this session changed are left uncommitted. The tree also carries other contributors' changes, which were not touched.

Execution: 2026-09-15, 17:51–18:00 +02:00, Windows 11, PowerShell. The coordinator was Opus 5 (1M context) at medium effort. No subagent was dispatched.

Changed files:

- `src/cadrumo/domain/calculations/registry/queries.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py`

Reused evidence, not rerun because the new claims do not depend on it:

- C11 and C12: the scoped `describe 131` run and the final `modelo list` run.
- C13: 10 passed.
- C14 and C15: static checks on the r02 files.

C13's `test_indexed_snapshot_uses_directory_endpoint_context_without_loading_prior_revision` and `test_a_dangling_review_comparison_is_refused_specifically` were not rerun. Their code paths did not change.

New command ledger (Command ID, Purpose, Exact command, Exit, Evidence):

- `R03-C01` | lint, format and types on the two changed files | `uv run --no-sync ruff check <2 files>`; `uv run --no-sync ruff format --check <2 files>`; `uv run --no-sync ty check <2 files>` | 0; 0; 0 | `All checks passed!`; `2 files already formatted`; `All checks passed!`
- `R03-C02` | console check | `uv run --no-sync aeat app modelo list` | 0 | header plus 58 rows; `036` 2, `038` 2, `100` 6, `131` 4, `303` 6
- `R03-C03` | focused regression | `uv run --no-sync pytest -o addopts= -p no:randomly -n 0 --strict-config --strict-markers --capture=sys --tb=short -ra -q src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py` | 0 | `10 passed in 171.54s`: the 8 existing view tests plus 2 new ones

The `131` count of 4 is checked against something independent of the listing: r02's C11 `describe 131` printed the revision ids `2019-2023, 2024, 2025, 2026`.

## Findings

### l01-r03-f01 | medium | Pinned `modelo list` counted and year-filtered the one-revision view instead of its directory

Contract: `ModeloListRow.revision_count` (`src/cadrumo/domain/calculations/registry/query_reports.py:78`) is the modelo's available revision count. The eager `RegistryQueryService.list_modelos` fills it from a complete `ModeloDefinition` (`len(modelo.revisions)`). The support matrix field of the same name is documented as "Number of registry revisions declared for this modelo" (`support_matrix.py:193`). The CLI renders it verbatim as `revisions`.

Defect: `PinnedRegistryQueryService.list_modelos` is the path the CLI uses. It read both `len(definition.revisions)` and the `--year` filter from the view that `ModeloRevisionDirectory.materialize` built around the latest revision. That view always carries exactly one revision. The count was therefore always 1. The year filter silently dropped any modelo whose only covering revision is not its latest. For example, `--year 2024` would have omitted 038, because `2024-desde-06` covers 2024 and `2025-y-siguientes` does not. The year-filter defect comes from the same misuse, and this session found it through source inspection. Its CLI symptom was not run.

Correction: the new `PinnedRegistryQueryService._latest_modelo_views` (`queries.py:872`) returns each directory paired with its view. `list_modelos` takes `revision_count` from `len(directory.revisions)` (`queries.py:911`) and the year coverage from the directory's `RevisionSelectionMetadata.period_selector` values. No extra revision is hydrated and no second registry read happens: the directory was already loaded to select the latest revision. `_modelo_covers_year` became `_selectors_cover_year` (`queries.py:1467`), which both the eager path (`queries.py:398`, behavior unchanged) and the pinned path use. `iter_modelo_definitions` keeps its signature and output.

Regression: `test_a_directory_backed_listing_counts_and_filters_by_every_directory_revision` builds a `FakeAuthorityComponentReader` holding the compiled 038 directory and both revision components. It asserts four things:

- The view carries only `2025-y-siguientes`.
- The row reports 2. That number comes from the two authored revisions, which the test asserts independently, not from the counting expression.
- `list_modelos(year=2024)` returns 038.
- The predecessor revision component is never loaded.

The test was not run against the unrepaired code.

### l01-r03-f02 | low | C13's indexed-snapshot test does not cover the repair; a published cross-revision snapshot case now does

What C13 proves: `test_indexed_snapshot_uses_directory_endpoint_context_without_loading_prior_revision` runs `PinnedAuthorityOperation.snapshot` through `directory.materialize` and the `RegistrySnapshot` nesting in `build_validated_snapshot`. It uses modelo 322 at revision `2023`, and it proves that the prior revision's payload is not loaded.

What it does not prove:

- Its reader is `FakeAuthorityComponentReader`, filled from the source-compiled bundled tree, not the published indexed authority.
- Revision 322/2023 declares `predecessor = { none = … }` and no `reviewed_against`. Its evolutions' `from_revision` is not an identity reference checked by `_validate_revisions`.
- It therefore has no cross-revision identity reference, and it would pass with or without the repair.

The lane01-r02 audit's limitation, that the snapshot path was not exercised for the repair, was correct in substance. Listing C13 under integrity evidence overstated it.

New coverage: `test_a_published_snapshot_keeps_its_cross_revision_view_valid_when_nested` opens `bundled_indexed_authority()`, the real published generation (read-only). It confirms the 038 directory declares both revisions. It then calls `operation.snapshot("038", filing_year=2025, period="01", grade=APPLICABILITY)`. The resulting `snapshot.modelo`, nested and revalidated inside `RegistrySnapshot`, carries only `2025-y-siguientes` with `reviewed_against` and `DeclaredPredecessor` both still `2024-desde-06`. The chain from published authority, through snapshot materialization, to nested validation is now exercised with a real cross-revision reference.

The fixture is the shared published artifact rather than an isolated copy. This matches existing `bundled_indexed_authority()` consumers, and the test does not write to it.

### l01-r03-f03 | low | view-validation scope is confined to `materialize`; no runtime path copies a view

Targeted source check of `ModeloDefinition._directory_revision_ids` (`schema.py:1375`) and `MODELO_REVISION_IDS_CONTEXT` (`schema.py:1293`):

- **Nested revalidation:** the scope is kept. `_validate_revisions` falls back to the private attribute when the context is absent (`schema.py:1421-1425`). Two tests cover this in the same `R03-C03` run: `test_a_view_stays_valid_inside_a_consumer_model_that_revalidates_it` (`ResolvedRegistryQueryContext`) and the new published snapshot test (`RegistrySnapshot`).
- **Serialized input:** the scope cannot enter this way. It is a pydantic `PrivateAttr`, not a field. `RegistryModel` uses `STRICT_FROZEN_CONFIG` with `extra="forbid"` (`src/cadrumo/core/models.py:47`). The only production code that sets the context key is `ModeloRevisionDirectory.materialize` (`temporal.py:156-159`). `dev/registry/eager_authority_baseline.py:148` passes a decode context without that key.
- **A complete modelo skipping complete-modelo checks:** not reachable. A freshly validated modelo defaults the attribute to `None`, and without the key it takes the complete branch. A view dumped and re-validated loses the attribute and is then refused as an incomplete complete-modelo, which fails closed. The two `test_a_complete_modelo_missing_…` tests cover this.
- **Source of the identity set:** the typed `ModeloRevisionDirectory` passed to `materialize`. Its validator enforces unique revision ids (`temporal.py:132-140`). At runtime it comes from `PinnedAuthorityOperation.modelo_directory` typed decoding. At compile time `from_modelo` builds it from a validated complete modelo.
- **Copy and update paths:** no production code calls `model_copy` or `model_validate` on a `ModeloDefinition` view. All `model_copy(update={"revisions": …})` sites are in tests or dev tooling, and they start from complete modelos.

Residual, not a present defect: pydantic `model_copy` copies private attributes. A future runtime caller that did `view.model_copy(update={"revisions": <full map>})` would get an object that looks complete but keeps view scope. On revalidation it would skip `validate_revision_predecessors` and `structural_succession_failures`. No such caller exists. No test was added because the failure mode has no current path.

### l01-r03-f04 | low | independent re-verification confirms the delivered count and test claims

A separate session re-checked this lane at 18:26–18:35 +02:00. That session had not written the lane's changes and changed no product or test file. Checkout: HEAD `eedac16053`. Inputs unchanged since the lane's own run: `queries.py` last written 17:56:13, `test_modelo_revision_directory_view.py` 17:56:06, `schema.py` 17:30:12.

- `V01` | console count | `uv run --no-sync aeat app modelo list` | exit 0 | header plus 58 rows. `036` 2, `038` 2, `100` 6, `131` 4, `303` 6. This matches `R03-C02`.
- `V02` | vault validation | `uv run --no-sync vaultspec-core vault check all --feature runtime-verification` | exit 0 | no warnings, run before this entry was appended.
- `V03` | focused regression | `uv run --no-sync pytest -o addopts= -p no:randomly -n 0 --strict-config --strict-markers --capture=sys --tb=short -ra -q src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py` | exit 0 | `10 passed in 299.62s`. This matches `R03-C03`. The run log is under `.logs/test-runs/2026-09-15/20260915T162844.499313Z-pytest-46084-f4b3c213`.

The static checks `R03-C01` were not re-run. This entry does not re-examine the source analysis in `l01-r03-f02` or `l01-r03-f03`.

## Recommendations

- For `l01-r03-f01`: the support matrix has the same count defect. `PinnedRegistryQueryService.support_matrix` feeds `iter_modelo_definitions()` views to `build_support_matrix_from_modelos`, and `support_matrix.py:266` sets `revision_count=len(modelo.revisions)`. Its view-derived fields (`revision_count`, `supported_revision_ids`) should be checked in a separately scoped lane. It was not changed or run here.
- For `l01-r03-f03`: if a runtime caller ever needs to widen a view, the follow-on decision is whether `ModeloDefinition` clears view scope on copy or refuses a copy of a view. That needs an ADR only if the change affects persisted or public contracts.
- Remaining unverified consumers:
  - the TUI launcher capture (`capture_law_selected_projection`)
  - casillas, formulas and bindings queries
  - the pinned support matrix
  - calculation, preview and filing paths
  - use from a built package

  This lane did not test any of them.
