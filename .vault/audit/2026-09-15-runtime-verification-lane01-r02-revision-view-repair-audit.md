---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:af83f1572f77b6342de51d624bcbf2ba4bf7a08d71e7e6cf84d3d90cb4ff9887'
related:
  - "[[2026-09-15-runtime-verification-lane01-r01-cli-reachability-audit]]"
---

# `runtime-verification` audit: `lane01-r02 revision view repair`

## Scope

Session `lane01-r02-revision-view-repair`. Implementation was authorized to repair the runtime revision-view validation defect `L01-R01-F02` from the linked lane01-r01 audit. Commit, push, and authority rebuild or publication were not authorized, and none happened. Checkout: worktree `Y:/code/cadrumo-worktrees/main`, branch `main`, HEAD `6574d6e553`. The touched production files had no uncommitted changes at session start. Execution 2026-09-15 17:10–17:37 +02:00, Windows 11, PowerShell. The coordinator ran the whole session; no subagent was dispatched.

Selected repair: a `ModeloDefinition` selected from a published `ModeloRevisionDirectory` resolves cross-revision identity references against the directory's complete revision identity set. A complete modelo keeps its existing validation unchanged. The published authority artifact is untouched.

Decision coverage: no accepted ADR found in `.vault/adr/` governs runtime modelo views. The repair keeps existing semantics: complete-modelo integrity rules are unchanged, and views get an identity-only check. It was treated as a routine implementation decision under this bounded authorization, so no new ADR was recorded.

Command ledger (Command ID, Purpose, Owner, Exact command, Exit, Evidence):

- `C01` | baseline | coordinator | `uv run --no-sync aeat app modelo list` | 1 | `Error. revision '2025-y-siguientes' has dangling review reference reviewed_against='2024-desde-06'; declared revisions are ['2025-y-siguientes']`
- `C02` | first regression run after the `reviewed_against`-only change | coordinator | `uv run --no-sync pytest -o addopts= -p no:randomly -n 0 --strict-config --strict-markers --capture=sys --tb=short -ra -q <view tests> <indexed-snapshot test> <compiler dangling test>` | 1 | `1 failed, 5 passed`; the view hit the predecessor-forest check
- `C03` | runtime check after the first change | coordinator | `uv run --no-sync aeat app modelo list` | 1 | `modelo '038' revision '2025-y-siguientes' declares predecessor '2024-desde-06', which is not a revision of this modelo`
- `C04` | syntax discovery | coordinator | `uv run --no-sync aeat app modelo describe --help` | 0 | `describe [OPTIONS] {modelo}` with `--year`, `--period`, `--as-of`
- `C05` | runtime check after the selected-view branch | coordinator | `uv run --no-sync aeat app modelo list` | 0 | header plus 58 modelo rows, including 038, 100, 131, 303, 309
- `C06` | additional path, unscoped | coordinator | `uv run --no-sync aeat app modelo describe 131` | 0 | selected revision 2026. Not probative: 131/2026 declares a no-predecessor root and no `reviewed_against`.
- `C07` | regression run after the selected-view branch | coordinator | same selection as C02 | 0 | `9 passed in 256.15s`
- `C08` | additional path, scoped to a referencing revision | coordinator | `uv run --no-sync aeat app modelo describe 131 --year 2025 --period 1T` | 1 | `revision '2025' has dangling review reference reviewed_against='2024'; declared revisions are ['2025']`
- `C09` | failure location | coordinator | scratch `python -c` that ran the CLI in-process and printed the stack when the error was constructed; no file written | 1 | the refusal came from `ResolvedRegistryQueryContext.__init__` (`queries.py:1059`) re-running `ModeloDefinition._validate_revisions`
- `C10` | revalidation mechanism | coordinator | scratch `python -c` building a view from the bundled indexed authority and nesting it | 0 | pydantic 2.13.5, no `revalidate_instances` config. The view built fine; nesting it in `ResolvedRegistryQueryContext` raised the dangling-review error.
- `C11` | additional path after the repair | coordinator | `uv run --no-sync aeat app modelo describe 131 --year 2025 --period 1T` | 0 | `Revisión 2025`, `Ids de revisión 2019-2023, 2024, 2025, 2026`, 35 casillas, 99 vinculaciones, 13 fórmulas
- `C12` | final `modelo list` | coordinator | `uv run --no-sync aeat app modelo list` | 0 | header plus 58 rows
- `C13` | final regression run | coordinator | same selection as C02 | 0 | `10 passed in 312.40s`
- `C14` | lint and format on the touched files | coordinator | `uv run --no-sync ruff check <6 files>`; `uv run --no-sync ruff format --check <6 files>` | 0; 0 | `All checks passed!`; `6 files already formatted`
- `C15` | types on the touched files | coordinator | `uv run --no-sync ty check <6 files>` | 0 | `All checks passed!`

Regression selection: `src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py`, `src/cadrumo/domain/calculations/registry/tests/test_snapshot_continuity_source_windows.py::test_indexed_snapshot_uses_directory_endpoint_context_without_loading_prior_revision`, and `dev/registry/tests/test_edition_materialisation_entry_point.py::test_a_dangling_review_comparison_is_refused_specifically`.

## Findings

### L01-R02-F01 | high | selected views ran whole-modelo cross-revision invariants in three places, not one

Confirmed mechanism, extending `L01-R01-F02`: `ModeloDefinition._validate_revisions` (`src/cadrumo/domain/calculations/registry/schema.py`) enforced three invariants that need the complete revision map: `reviewed_against` membership, the `validate_revision_predecessors` forest and date agreement, and `structural_succession_failures`. The single-revision view from `ModeloDirectoryMetadata.materialize` failed all of them whenever the selected revision referenced another revision.

The published revision payload keeps `predecessor`. C02 and C03 confirm this: after `reviewed_against` was repaired, the forest check failed. Only modelos 100/2022 and 309/2016-2017 declare structural successions.

Pydantic runs a model-level after-validator again whenever an existing instance is placed in another model's field, and the construction context is not available then (C09, C10). So a view built with validation context was re-checked without it inside `ResolvedRegistryQueryContext`. C06 did not expose this because 131/2026 carries no cross-revision reference; C08 did.

### L01-R02-F02 | low | repair: selected views resolve identity references against their directory

Changed source:

- `src/cadrumo/domain/calculations/registry/schema.py`
  - New `MODELO_REVISION_IDS_CONTEXT` key and `_context_revision_ids` helper.
  - New `_validate_selected_view_references`. It refuses view revisions outside the directory, a `DeclaredPredecessor` target outside it, and structural-succession endpoints outside it or not ending at the carrying revision.
  - New private attribute `ModeloDefinition._directory_revision_ids`, set from the context on first validation. Re-validation of the same instance by a consumer model reuses it.
  - `_validate_revisions` checks `reviewed_against` against the directory set for a view, or against the modelo's own revisions otherwise. Only a complete modelo runs `validate_revision_predecessors` and `structural_succession_failures`.
- `src/cadrumo/domain/calculations/registry/temporal.py`: `materialize` moved from `ModeloDirectoryMetadata` to `ModeloRevisionDirectory`, which owns the complete revision identities. It validates through `ModeloDefinition.model_validate(..., context=...)`. The old method was deleted.
- Call sites moved from `directory.modelo.materialize` to `directory.materialize`:
  - `src/cadrumo/domain/calculations/registry/queries.py` (`iter_modelo_definitions`, `_context`)
  - `src/cadrumo/domain/calculations/registry/authority.py` (`snapshot`)
  - `src/cadrumo/entrypoints/tui/launcher.py` (`capture_law_selected_projection`)
- Added `src/cadrumo/domain/calculations/registry/tests/test_modelo_revision_directory_view.py`: eight tests on the compiled bundled registry, with no test doubles.

Why integrity is preserved:

- A complete `ModeloDefinition` (no context, no private identity set) runs exactly the previous checks. A view never skips an identity reference: each one must resolve to a revision the typed directory declares. `reviewed_against` is neither dropped nor rewritten.
- Only invariants that compare other revisions' payloads are left to complete-modelo validation, which the directory's source modelo passed when it was compiled. The compiler builds complete definitions in `load_modelo_directory` (`dev/registry/compiler/loader.py:158`), and `ModeloRevisionDirectory.from_modelo` takes that validated `ModeloDefinition`.
- The private attribute cannot be authored from TOML or serialized. Only `materialize` sets it, through validation context.

Before and after: `modelo list` exit 1 (C01), then exit 0 with 58 rows (C12). The scoped `describe 131 --year 2025 --period 1T` exit 1 (C08), then exit 0 selecting revision 2025 (C11).

Integrity evidence in C13 (10 passed):

- A view keeps `reviewed_against` and `predecessor` pointing at 038/2024-desde-06.
- A view survives nesting in `ResolvedRegistryQueryContext`.
- A view refuses a dangling `reviewed_against` ('2023'), a dangling predecessor ('2023'), a revision the directory does not declare ('2030'), and a structural-succession endpoint outside the directory ('1999', modelo 100).
- A complete modelo missing the reviewed revision is refused, and so is one missing the named predecessor.
- The compiler loader still refuses a dangling review comparison (`test_a_dangling_review_comparison_is_refused_specifically`).
- The existing indexed-snapshot test on 322 still passes.

The consumer-revalidation test targets the defect that C08 reproduced and C10 isolated. It was added after that reproduction. None of the new tests was run against the original, unrepaired code; the before-state evidence is the runtime failures C01 and C08 and the intermediate failure C02.

### L01-R02-F03 | low | remaining limitations

- The `revisions` column of `aeat app modelo list` reports 1 for every modelo, because `list_modelos` counts the view's revisions (`queries.py:895`, `revision_count=len(definition.revisions)`). `describe 131` reports four revision ids. This comes from the view construction introduced before this session, not from this repair. It was observed but not changed.
- Verified runtime paths: `modelo list` (unscoped latest views) and scoped `describe` through `_context`. Not exercised: `PinnedAuthorityOperation.snapshot` (`authority.py:749`, nested in `RegistrySnapshot`), the TUI launcher capture, casillas/formulas/bindings queries, and any calculation or filing path. The revalidation mechanism is shared, but those paths were not run.
- The predecessor date-agreement and succession lineage-ownership invariants are not re-checked in views. That is correct only as long as directories come from validated complete modelos. A hand-built `ModeloRevisionDirectory` with inconsistent metadata would not be caught by the view.

## Recommendations

- For `L01-R02-F03`: decide whether `aeat app modelo list` should report the directory's revision count instead of the view's. That is a routine query fix, but it changes visible output and was out of scope here.
- For `L01-R02-F03`: the next evidence lane should exercise one `RegistrySnapshot`-producing runtime path (for example a bindings or casillas query scoped to a revision with a cross-revision reference) to confirm the snapshot nesting path.
