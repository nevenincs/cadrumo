---
tags:
  - '#exec'
  - '#modelo-347-fileability'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:6ef04cc3989dab7fe977851c87dd5bb2d4cd6d90dacc79e14ac3db64e085978f'
related:
  - "[[2026-10-03-modelo-347-fileability-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-347-fileability` ledger

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

- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/iva-flow.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/bindings/0001-declarations.toml`
- `S01` `verify:` `inspect_authoring_candidate` -> `pass`
- `S02` `A` `src/cadrumo/_data/registry/aeat/facts/0148-m347-clave-threshold-buckets.toml`
- `S02` `M` `src/cadrumo/domain/calculations/registry/m347_threshold.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`
- `S02` `A` `src/cadrumo/domain/calculations/registry/tests/test_m347_threshold_buckets.py`
- `S02` `A` `dev/registry/tests/test_m347_threshold_buckets_authored.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_resolver.py`
- `S02` `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py`
- `S02` `verify:` `pytest test_m347_threshold_buckets` -> `pass`
- `S02` `verify:` `ruff check` -> `pass`
- `S02` `verify:` `ty check` -> `pass`
- `S10` `M` `src/cadrumo/domain/calculations/registry/schema_revision_members.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/applicability_payer_facts.py`
- `S10` `M` `dev/registry/compiler/validate_applicability_section.py`
- `S10` `M` `src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/applicability/0001-declarations.toml`
- `S10` `A` `dev/registry/tests/test_applicability_exclusions.py`
- `S10` `M` `dev/registry/tests/test_payer_fact_declarations.py`
- `S10` `M` `dev/registry/tests/test_modelo_applicability.py`
- `S10` `M` `src/cadrumo/application/overview/tests/test_applicability.py`
- `S10` `verify:` `pytest applicability suites` -> `pass`
- `S10` `verify:` `inspect_authoring_candidate` -> `pass`
- `S10` `verify:` `ruff check` -> `pass`

## Notes

- `S01` stand-in rd-1065-2007-art-31.html and its sidecars are unreferenced and await deletion at Phase close
- `S02` 44 tests that read the published authority await the P01 Phase-close publication
- `S10` `applicability_payer_facts.py` includes another writer's helper split of the new code; published-authority tests await Phase publication
