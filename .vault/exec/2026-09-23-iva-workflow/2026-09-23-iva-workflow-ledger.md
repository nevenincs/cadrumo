---
tags:
  - '#exec'
  - '#iva-workflow'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:286e83508b56bac746d29bbef57d194ce5d1402500c29beecd6f69816ed38bca'
related:
  - "[[2026-09-23-iva-workflow-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `iva-workflow` ledger

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
- `S01` `M` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `S01` `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `S01` `M` `src/cadrumo/application/filing/export_producer.py`
- `S01` `M` `src/cadrumo/application/filing/projection.py`
- `S01` `M` `src/cadrumo/application/modelo/m303_filing_evidence.py`
- `S01` `M` `src/cadrumo/application/filing/tests/test_producer_snapshot.py`
- `S01` `verify:` `pytest -m 'unit or integration' application/filing/tests domain/modelos/tests + M303 evidence suites: 707 passed` -> `pass`

## Notes

- `S01` 6 failures in adapters/persistence/profile/tests/test_m303_filing_evidence_validation.py (ModeloProfileReadinessError profile_absent/inactive) reproduce identically at committed source 976971d1be before this Step; pre-existing, reported. 1 failure is the retired-token guard awaiting the error rename.
