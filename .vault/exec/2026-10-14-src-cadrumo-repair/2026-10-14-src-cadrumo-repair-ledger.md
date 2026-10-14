---
tags:
  - '#exec'
  - '#src-cadrumo-repair'
date: '2026-10-14'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:212da267990b0f65bdef3350900d7195e8d576e4a8b7dc52b0eb4c0ea06e5a95'
related:
  - "[[2026-10-14-src-cadrumo-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `src-cadrumo-repair` ledger

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

- `S03` `M` `src/cadrumo/core/diagnostic_log.py`
- `S03` `M` `src/cadrumo/core/tests/test_logging_first_record.py`
- `S03` `M` `src/cadrumo/core/tests/test_logging_rotation.py`
- `S03` `verify:` `focused logging-and-markers.log 15 tests` -> `pass`
- `S03` `verify:` `focused diagnostic context checks in owned-gates-final.log` -> `pass`
- `S03` `by:` `root`
- `S08` `M` `src/cadrumo/application/aggregation/evidence_advisory.py`
- `S08` `A` `src/cadrumo/application/aggregation/tests/test_calculation_revision_iva_evidence_authority.py`
- `S08` `M` `src/cadrumo/application/tests/test_reference_catalogue.py`
- `S08` `M` `src/cadrumo/application/tests/test_apoderado_scopes_payload.py`
- `S08` `M` `src/cadrumo/tests/test_spanish_iva_stem_conformance.py`
- `S08` `verify:` `focused filing-frame IVA evidence regression (3 tests)` -> `pass`
- `S08` `verify:` `IVA stem and scope payload guards (11 tests)` -> `pass`
- `S08` `by:` `root`
- `S07` `D` `src/cadrumo/_data/corpus/tests/test_corpus_provenance.py`
- `S07` `D` `src/cadrumo/_data/corpus/tests/__init__.py`
- `S07` `A` `dev/quality/tests/test_corpus_provenance.py`
- `S07` `M` `dev/registry/compiler/source_evidence_fingerprint.py`
- `S07` `M` `dev/registry/compiler/corpus_catalogue.py`
- `S07` `M` `dev/registry/compiler/legal_grounding.py`
- `S07` `M` `dev/registry/tests/test_source_evidence_fingerprint_bound.py`
- `S07` `M` `dev/registry/tests/test_authority_artifact_currency.py`
- `S07` `M` `dev/registry/compiler/tests/test_manual_source_identity.py`
- `S07` `M` `dev/registry/conformance/tests/test_validator_source_evidence.py`
- `S07` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check.py`
- `S07` `M` `.authority/authority.current.json`
- `S07` `A` `.authority/authority-2549cff818c899d53e0e5884eb764082f16ce37d461ebb183dac648c9c8a647c.sqlite3`
- `S07` `verify:` `focused corpus ownership and evidence currency modules (37 tests)` -> `pass`
- `S07` `verify:` `explicit Python-control source/legal enrollment refusal (4 tests)` -> `pass`
- `S07` `verify:` `scoped Ruff lint and formatting` -> `pass`
- `S07` `verify:` `python -m dev.registry.pipeline publish-authority (identity 66af11543946175d3d2b85399d6132b5d1f4a0f4a60a0c3d3732db1538d02dba)` -> `pass`
- `S07` `verify:` `just check-registry-gate (valid, runtime-load, integrity)` -> `pass`
- `S07` `by:` `root`

## Notes

- `S03` Unrelated concurrent edits and index state preserved; no mixed-source commit created.
- `S08` No mixed-source commit: other sessions concurrently modify the shared worktree and index; preserve their changes.
- `S07` No mixed-source commit: concurrent sessions modify the shared worktree and index; no legal payload was rewritten.
