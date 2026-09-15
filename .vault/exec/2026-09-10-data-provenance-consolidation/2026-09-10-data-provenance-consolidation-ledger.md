---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:7d7b2e69eff0f33794a4941e29a52d1dcad7e818bcd9b1443e0e3c881f9af75c'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `data-provenance-consolidation` ledger

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
- `S01` `A` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S01` `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S01` `verify:` `uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S01` `verify:` `uv run python -m py_compile src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S02` `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ty check src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S03` `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S03` `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ty check src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> `pass`
- `S04` `A` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `S04` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py` -> `pass`
- `S05` `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `S05` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py` -> `pass`
- `S06` `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `S06` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py` -> `pass`
- `S07` `M` `src/cadrumo/domain/calculations/registry/corpus_catalogue.py`
- `S07` `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `S07` `M` `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`
- `S07` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py -k conflicting_identity` -> `pass`
- `S08` `T`
- `S09` `T`
- `S10` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S10` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S11` `M` `dev/corpus/tests/test_record_design_support.py`
- `S11` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S12` `M` `dev/corpus/tests/test_record_design_support.py`
- `S12` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S13` `M` `dev/docs/preprocess/sidecar.py`
- `S13` `verify:` `uv run pytest dev/docs/preprocess/tests/test_sidecar_contract.py -q` -> `pass`
- `S14` `M` `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`
- `S14` `verify:` `uv run pytest dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -q` -> `pass`
- `S15` `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `S15` `verify:` `uv run --no-sync pytest dev/corpus/tests/test_extraction_sidecar_freshness.py::test_committed_extraction_sidecars_match_current_sources -q` -> `pass`
- `S16` `D` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json`
- `S16` `verify:` `git diff --check -- src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json` -> `pass`
- `S17` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S17` `verify:` `uv run python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `S18` `M` `dev/corpus/tests/test_record_design_support.py`
- `S18` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py` -> `pass`
- `S19` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S19` `M` `dev/corpus/tests/test_record_design_support.py`
- `S19` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S20` `M` `src/cadrumo/_data/corpus/tests/test_corpus_provenance.py`
- `S20` `verify:` `uv run pytest src/cadrumo/_data/corpus/tests/test_corpus_provenance.py -q` -> `pass`
- `S21` `T`
- `S21` `verify:` `uv run pytest dev/registry/tests/test_corpus_provenance_coverage.py -q` -> `pass`
- `S22` `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `S22` `verify:` `uv run ruff check dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S23` `M` `dev/corpus/tests/test_record_design_support.py`
- `S23` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S24` `M` `dev/registry/compiler/authority.py`
- `S24` `M` `dev/registry/tests/test_authority_publication.py`
- `S24` `M` `src/cadrumo/tests/registry_snapshot.py`
- `S24` `M` `dev/registry/tests/_referential_integrity_support.py`
- `S24` `verify:` `uv run pytest -n0 dev/registry/tests/test_authority_publication.py -q` -> `pass`
- `S25` `M` `dev/corpus/tests/test_record_design_support.py`
- `S25` `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.json`
- `S26` `M` `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-95.html.extracted.json`
- `S26` `verify:` `uv run pytest -n0 dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -q` -> `pass`
- `S26` `verify:` `uv run pytest -n0 dev/corpus/tests/test_extraction_sidecar_freshness.py -q` -> `pass`
- `S26` `verify:` `uv run pytest -n0 dev/corpus/tests/test_extract_boe_article.py dev/registry/tests/test_oracle_parity.py -q` -> `pass`
- `S26` `verify:` `uv run pytest -n0 dev/registry/tests/test_generated_export_trees.py -q` -> `pass`

## Notes

- `S15` Full-module validation is pre-existing red at the canonical-LF gate for six normative HTML files; baseline formatting also fails outside this Step's diff.
- `S16` The loader remains until S17, so its synchronizer validation must run after that paired removal.
- `S17` Committed atomically with S16 and S18 because either intermediate revision would be unrunnable.
- `S18` Committed atomically with S16 and S17 because either intermediate revision would be unrunnable.
- `S21` S08 already removed the retired sweep; S21 verified the retained catalog-backed detector module without further source edits.
- `S22` The full module retains a pre-existing canonical-LF fixture failure; focused retained tests exceeded the local command cap.
