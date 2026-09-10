---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:6c0df46f823aaac343b793752b43624708eb170c9050c0ec24da18f07693865f'
step_id: 'S61'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [S | opus-medium] Add the declared-predecessor date-agreement rule: where an edition names a predecessor and the two editions do not overlap in validity, the predecessor must be the earlier one; overlapping editions are exempt, and that exemption is exactly the parallel-variant case. Also make the lineage totality rule follow a named predecessor edge instead of the adjacent edition. Both land before the first modelo migrates. Proof: a successor naming a later non-overlapping edition is refused naming both; an overlapping pair loads; a totality fixture with a named non-adjacent predecessor resolves against the named edition.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/period_selector_overlap.py`
- `A` `src/cadrumo/domain/calculations/registry/revision_predecessor_date_agreement.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_date_agreement.py`
- `M` `src/cadrumo/domain/calculations/registry/revision_order.py`
- `M` `src/cadrumo/domain/calculations/registry/revision_predecessor_forest.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/casilla_lineage_totality.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_totality.py`
- `verify:` `pytest` date agreement, totality, forest, predecessor declaration, modelo 369, cross-revision divergence, totality gate -> `pass` (83)
- `verify:` totality reverted to adjacency, date rule neutralised, overlap exemption removed -> `fail` (planted), restored by copy
- `verify:` `pytest` cross-revision and lineage suites -> `pass` (103)
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass` (exit 0)
- `verify:` `ruff format`, `ruff check`, `ty check` on changed Python -> `pass`

## Notes

`test_docstring_cross_reference_targets.py` and `test_qualified_docstring_references_resolve.py` fail with 8 tests, reporting defects across the whole source tree. None of the reported defects is in a file or line this Step changed. The failures were not re-run against a baseline worktree.

The reviewer persona could not be launched from this session, so the mandatory code review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the diffs against the ADR. The overlap helper was moved to a public module with no shim. Enrolment sits beside the forest check, and a same-start non-overlapping pair fails closed. Re-run: 100 tests passed, `registry verify` exit 0, ruff and ty clean. None of the docstring-reference failures names a file this Step changed.
