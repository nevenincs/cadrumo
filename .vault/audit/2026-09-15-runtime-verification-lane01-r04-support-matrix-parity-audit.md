---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:18af501d816e7d5de2bc13abcc02217ca6cc95457848448595e74cdd8fdbf291'
related:
  - "[[2026-09-15-runtime-verification-lane01-r03-view-contract-closure-audit]]"
---

# `runtime-verification` audit: `lane01-r04 support matrix parity`

## Scope

Session `lane01-r04-support-matrix-parity`, continuing the lane01-r03 view contract closure audit. That audit's handoff was mislabelled "lane 2" but belongs to lane01-r03, which this chain keeps.

Authorized work:

- Fix the pinned support matrix's `revision_count`.
- Determine whether `supported_revision_ids` also derives from the one-revision view.
- Add focused regression coverage.

Not authorized, and not done: commit, push, authority publication, and any TUI, calculation, filing or packaging work.

Checkout: worktree `Y:/code/cadrumo-worktrees/main`, branch `main`, HEAD `eedac16053` at start. HEAD moved during the session to `9fe7a274c5`: the worktree's sync automation added three commits, and nobody in this session committed. Commit `735b1247a6` captured the three changed source files, including the earlier r03 diff, and `3877e71430` captured this audit's scaffold. At the start, `queries.py` and the test file carried only the uncommitted r03 diff (79 insertions, 14 deletions). Other contributors had changed `snapshot.py`, `tests/published_authority.py` and `tests/test_modelo_100_imputed_real_estate_art85.py`, and added `tests/test_irnr_registry_tokens.py` untracked. None of those was touched.

Execution: 2026-09-15, 18:28–18:36 +02:00, Windows 11, PowerShell. Coordinator: Opus 5 (1M context), medium effort. No subagent was dispatched.

Changed files, committed by sync automation in `735b1247a6` rather than left uncommitted as instructed:

- `src/cadrumo/domain/calculations/registry/support_matrix.py`
- `src/cadrumo/domain/calculations/registry/queries.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py`

Reused evidence, not rerun:

- The r03 listing and published-snapshot tests.
- r03's `modelo list` counts: 038=2, 100=6, 131=4.
- r02's C11 `describe 131` revision ids.

Command ledger. Each tool invocation counts separately.

- `R04-C01` | CLI syntax discovery | `uv run --no-sync aeat app modelo support-matrix --help` | exit 0 | the command takes no scoping options, so the smallest invocation is the whole matrix. Its cost is the same point-loaded directory walk as `modelo list`.
- `R04-C02` | CLI check | `uv run --no-sync aeat app modelo support-matrix` | exit 0 | header plus 58 rows. `revs` column: 038 → 2 (latest `2025-y-siguientes`), 100 → 6 (latest `2025`), 131 → 4 (latest `2026`). These agree with r03's `modelo list` counts and with r02's `describe 131` ids.
- `R04-C03` | lint on the 3 changed files, for the renamed builder import and the `__all__` entry | `uv run --no-sync ruff check <3 files>` | exit 0 | `All checks passed!`
- `R04-C04` | format on the 3 changed files, for the new multi-line generator expressions | `uv run --no-sync ruff format --check <3 files>` | exit 0 | `3 files already formatted`
- `R04-C05` | types on the 3 changed files, for the new `TYPE_CHECKING` import of `ModeloRevisionDirectory` and the pair-typed builder | `uv run --no-sync ty check <3 files>` | exit 0 | `All checks passed!`
- `R04-C06` | focused regression | `uv run --no-sync pytest -o addopts= -p no:randomly -n 0 --strict-config --strict-markers --capture=sys --tb=short -ra -q <view test file>::test_a_directory_backed_support_matrix_reports_every_declared_revision <view test file>::test_a_directory_backed_listing_counts_and_filters_by_every_directory_revision` | exit 0 | `2 passed in 278.76s`. The listing node was included because its setup was moved into the shared `_pinned_service` helper.

## Findings

### l01-r04-f01 | medium | Pinned support matrix reported `revision_count` and `supported_revision_ids` from the one-revision view

Contract, from the canonical definition of `ModeloEntry` (`src/cadrumo/domain/calculations/registry/support_matrix.py`):

- `revision_count` is "Number of registry revisions declared for this modelo" (line 197).
- `supported_revision_ids` is "Every declared revision id, oldest `valid_from` first" (line 202).

Neither field carries a support or applicability condition. The eager producer `build_support_matrix` computes both from the complete `ModeloDefinition.revisions`. The only consumers are CLI rendering and the JSON payload: `_modelo_discovery_rendering.py:392-395`, `_modelo_support_matrix_payloads.py:46-49`, and the `revs` column in `_modelo_discovery_cli.py`. None of them filters or reinterprets the fields. The existing eager test `test_build_support_matrix_is_never_a_fabricated_positive` pins `revision_count == len(modelo.revisions)`. So, under the field's own contract, "supported revision ids" and "all available revision ids" are the same set. The first field is the length of the second.

Defect, confirmed for both fields: the pinned `PinnedRegistryQueryService.support_matrix` passed `iter_modelo_definitions()` views to `build_support_matrix_from_modelos`, which derived both fields from `modelo.revisions`. On a view that is exactly one revision, the selected latest one. Every pinned row therefore reported `revision_count` 1 and `supported_revision_ids` holding only the latest id. `latest_revision_id`, the capability predicates, renames and portal references were already correct, because they read the latest revision, which is the one the view carries.

Correction:

- `_entry_for_modelo` (`support_matrix.py:251`) now takes the declared revision ids explicitly, and `revision_count` is their length (line 267).
- The eager `build_support_matrix` (line 282) passes the complete modelo's revision ids, sorted by `(valid_from, id)`. That matches the previous expression, so eager behavior is unchanged.
- `build_support_matrix_from_modelos` was replaced by `build_support_matrix_from_directory_views` (line 309). It takes the `(ModeloRevisionDirectory, ModeloDefinition)` pairs from the r03 `_latest_modelo_views` helper, and reads the ids and ordering from the directory's `RevisionSelectionMetadata`.
- The old function had one consumer. It was deleted, along with its `__all__` entry, and `queries.py:918` was updated.
- No further revision is loaded, and the directory is the one already loaded to choose the latest revision. Filtering does not exist here. Ordering and capability semantics are unchanged.

Regression: `test_a_directory_backed_support_matrix_reports_every_declared_revision` uses 038 through a `FakeAuthorityComponentReader` holding the compiled directory and both revisions. The shared `_pinned_service` helper (`tests/test_modelo_revision_directory_view.py:55`) builds that reader. The test first asserts, independently of the code, that `2024-desde-06` starts before `2025-y-siguientes`. It then checks the three separate sets:

- The materialized view carries only `2025-y-siguientes`.
- `latest_revision_id` is `2025-y-siguientes`.
- `supported_revision_ids` is `("2024-desde-06", "2025-y-siguientes")`, and `revision_count` is 2.

Eager-to-pinned comparison over the same controlled inputs was not added. The eager builder only accepts a `ValidatedRegistryAuthority`, which would mean loading the whole registry. Eager behavior stays covered by the existing `test_support_matrix.py`, which was not rerun because its producer expression did not change. The new test was not run against the unrepaired code.

### l01-r04-f02 | low | Clarifications to lane01-r03 evidence, recorded without rerunning it

- The pinned `modelo list --year` defect (`l01-r03-f01`) was found by reading source. Its CLI symptom was never reproduced. The regression test proves the corrected filter, not the historical CLI failure.
- `test_a_published_snapshot_keeps_its_cross_revision_view_valid_when_nested` supplies the cross-revision snapshot coverage that r02's C13 test lacked. C13's 322/2023 case has no cross-revision identity reference.
- r03's single vault check (`vault check all --feature runtime-verification --fix`) exited 1: 1816 errors under `.vault/.trash/`, plus a stale feature index. The index was then regenerated successfully, but no later check was run in r03, so r03 never established that the feature was clean after that step. This session previewed the feature check without `--fix` (`R04-C07`: `vaultspec-core vault check all --feature runtime-verification`, exit 1). Its findings, apart from the unchanged trash errors, were limited to two mechanical items: this audit's stale modified stamp, and a stale feature index (6 links for 7 documents). Only those were applied, through `--fix` and `vaultspec-core vault feature index -f runtime-verification`.

Application results:

- `R04-C08` (`--fix`) exited 1 with 4 fixed. Inspecting the affected paths showed three things:
  - This audit was re-stamped.
  - The r03 audit's `body_hash` was re-attested, with no body change against HEAD.
  - A new, empty `lane03-r03-binding-value-audit` scaffold, created at the same time by another session, now raises three body-section warnings. It is not this lane's document and was left untouched.
- `R04-C09` (`feature index`) exited 0.

After the source-state correction above, one more `--fix` run re-stamped this audit. No check after it establishes final cleanliness.

### l01-r04-f03 | low | 036 `latest` column renders a digest-like revision id; observed, not investigated

In `R04-C02`, modelo 036's `latest` column read `sha256:04bcf3b9-siguientes`, while every other row showed a plain revision id. It is unrelated to the count defect and outside this lane's scope. It may be a display redaction of an identifier or an authored id, and neither was checked.

## Recommendations

- For `l01-r04-f03`: a separately scoped evidence question is whether the pinned 036 directory's latest revision id is authored as shown or is rewritten by CLI rendering. Compare `operation.modelo_directory("036").revisions` with the text renderer.
- Remaining limitations from lane01-r03 still stand:
  - Untested consumers: TUI launcher capture, casillas/formulas/bindings queries, calculation, preview and filing paths, and built-package adoption.
  - The documented latent `model_copy` view-scope risk, which has no current caller and is not a work item.
