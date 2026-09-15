---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:2c13ad046baebeb8d971e23bb27a9fd2a87810869f70ed59efd6915f3d2f4cb4'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `aeat-design-relayout-boundary` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `S01` `verify:` `uv run --no-sync python -m dev.registry.analysis.m200_2024_full_reconciliation` -> `pass`
- `S01` `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_full_reconciliation.py dev/registry/tests/test_m200_2024_full_reconciliation.py` -> `pass`
- `S02` `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `S02` `verify:` `uv run --no-sync pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
- `S02` `verify:` `git diff --check -- dev/registry/analysis/m200_2024_full_reconciliation.py dev/registry/tests/test_m200_2024_full_reconciliation.py` -> `pass`
- `S03` `M` `dev/registry/analysis/m200_2024_restoration_candidates.py`
- `S03` `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_restoration_candidates.py` -> `pass`
- `S04` `M` `dev/registry/tests/test_m200_2024_restoration_candidates.py`
- `S04` `verify:` `uv run --no-sync pytest -q -n 0 dev/registry/tests/test_m200_2024_restoration_candidates.py` -> `pass`
- `S05` `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `S05` `verify:` `uv run --no-sync python -m pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
- `S06` `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `S06` `verify:` `uv run --no-sync python -m pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
- `S07` `M` `dev/registry/analysis/m200_semantic_casilla_candidates.py`
- `S07` `verify:` `uv run python -m dev.registry.analysis.m200_semantic_casilla_candidates` -> `pass`
- `S07` `verify:` `uv run pytest dev/registry/tests/test_m200_semantic_casilla_candidates.py -q -n0` -> `pass`
- `S07` `verify:` `uv run ruff check dev/registry/analysis/m200_semantic_casilla_candidates.py` -> `pass`
- `S08` `M` `dev/registry/tests/test_m200_semantic_casilla_candidates.py`
- `S08` `verify:` `uv run pytest dev/registry/tests/test_m200_semantic_casilla_candidates.py -q -n0` -> `pass`
- `S08` `verify:` `uv run ruff check dev/registry/tests/test_m200_semantic_casilla_candidates.py` -> `pass`
- `S09` `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `S09` `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `S09` `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_exposes_open_authority -q` -> `pass`
- `S10` `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `S10` `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `S10` `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text -q` -> `pass`
- `S11` `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `S11` `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `S11` `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_refuses_missing_unknown_wrong_and_later_year_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_cli_legal_admission_refuses_an_open_worklist_and_pending_authority -q` -> `pass`
- `S15` `T`

## Notes

- `S03` Historic restoration remains proposal-only: the renderer emits TOML to stdout and the module has no destination-path argument or filesystem-writing helper.
- `S03` Removed the unused historic-candidate compatibility alias and builder; the proposal-only API is now the sole exported surface.
- `S03` The semantic-map source reference and SHA-256 must exactly match the parsed pinned design source before historic evidence is joined.
- `S04` The CLI parser rejects filesystem destination options, and captured stdout is deterministic proposal-only TOML without a `revisions` table.
- `S04` Runtime coverage forbids filesystem write calls and asserts that no destination-path writer surface or retired aliases is exported.
- `S04` Real `SemanticMap`/official-design joining and coordinated map-plus-gap source-drift refusal remain covered.
- `S04` Mutation detectors cover target description, semantic role, legal references, and source SHA; source identity is checked against the parsed pinned design.
