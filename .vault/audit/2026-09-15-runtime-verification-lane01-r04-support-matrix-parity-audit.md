---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:40d9e6615be39dc5ae1272a25312529d36c6a53e3aec8e3b2160f8086983a9ec'
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

Checkout: worktree `Y:/code/cadrumo-worktrees/main`, branch `main`. HEAD was `eedac16053` at the start. At that point `queries.py` and the test file carried only the uncommitted r03 diff (79 insertions, 14 deletions). Other contributors had changed `snapshot.py`, `tests/published_authority.py` and `tests/test_modelo_100_imputed_real_estate_art85.py`, and added `tests/test_irnr_registry_tokens.py` untracked. None of those was touched.

Commit state, distinguishing what was tested from later HEAD movement:

- Tested content: every check in the ledger below ran against the working-tree state of the three changed source files at 18:30–18:35 +02:00.
- Source commit: the worktree's sync automation committed exactly that content in `735b1247a6`. Nobody in this session committed.
- Audit scaffold: committed by the same automation in `3877e71430`.
- Later movement: HEAD reached `53a45a04ef` by session close. None of the commits after `735b1247a6` was tested by this lane.
- This audit: its final body edits remain uncommitted.

Execution: 2026-09-15, 18:28–18:45 +02:00, Windows 11, PowerShell. Coordinator: Opus 5 (1M context), medium effort. No subagent was dispatched.

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
- r03's single vault check exited 1: 1816 errors under `.vault/.trash/`, plus a stale feature index. The index was then regenerated successfully, but no later check was run in r03, so r03 never established that the feature was clean after that step.

Vault reconciliation in this session:

- `R04-C07`, a feature check without `--fix`, exited 1. Its only findings besides the trash errors were this audit's stale modified stamp and a stale feature index (6 links for 7 documents).
- `R04-C08`, the feature check with `--fix`, exited 1 with 4 fixed. It re-stamped this audit and re-attested the r03 audit's `body_hash`, with no body change against HEAD. It also flagged the `lane03-r03-binding-value-audit`, which another session was authoring at the same time and which was left untouched.
- `R04-C09`, `vaultspec-core vault feature index -f runtime-verification`, exited 0.
- `R04-C10`, the feature check with `--fix` after the commit-state correction, exited 1. The only remaining errors were the 1816 trash errors; `features`, `body-sections` and `modified-stamp` were clean, with 1 fixed (this audit's stamp).

This closing record was written with one guarded body edit instead of another feature-wide fixer, so no later feature check was run.

### l01-r04-f03 | low | 036 `latest` column shows `sha256:04bcf3b9-siguientes`; unclassified observation

In `R04-C02`, modelo 036's `latest` column read `sha256:04bcf3b9-siguientes`, while every other row showed a plain revision id. This lane did not investigate it. Its appearance alone does not establish a defect, and it is recorded without classification.

## Recommendations

- For `l01-r04-f03`: if pursued, a separately scoped evidence question is whether 036's latest revision id is authored as shown or is rewritten during rendering.
- Closing status: the revision-view repair, the listing metadata and the support-matrix metadata are verified within the boundaries recorded in the lane01-r02, lane01-r03 and lane01-r04 audits.
- Still unverified: the TUI, other queries (casillas, formulas, bindings), calculation, preview and filing paths, and built-package adoption.
- The latent `model_copy` view-scope risk stays documented, with no current caller and no work item.
