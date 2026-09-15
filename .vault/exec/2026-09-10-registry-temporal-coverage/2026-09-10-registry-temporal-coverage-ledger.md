---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:697e741d438f108616dd02e0d3c2033c127bc897e739af883e85eadb8a593fc7'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-temporal-coverage` ledger

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
- `S01` `A` `src/cadrumo/domain/calculations/registry/corpus_provenance.py`
- `S01` `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/corpus_provenance.py src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py` -> `pass`
- `S02` `A` `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py`
- `S02` `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py -q` -> `pass`
- `S03` `M` `src/cadrumo/domain/calculations/registry/legal.py`
- `S03` `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_committed_registry_legal_and_construct_references_validate_through_loader -q` -> `pass`
- `S04` `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`
- `S04` `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_attested_and_reviewed_presumptive_legal_corpus_remain_accepted src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_reviewed_presumptive_exception_set_exactly_covers_committed_legal_corpus src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_authored_or_unreviewed_presumptive_normative_corpus_is_refused -q` -> `pass`
- `S05` `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `S05` `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority"` -> `pass`
- `S06` `M` `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `S06` `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_authority.py::test_authority_exposes_validated_legal_corpus_provenance -q` -> `pass`
- `S24` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `S24` `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S25` `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `S25` `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S26` `M` `src/cadrumo/_data/registry/aeat/legal/censo.toml`
- `S26` `verify:` `test_registry_legal_grounding.py` -> `pass`
- `S27` `D` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`
- `S27` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `S27` `A` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `S27` `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S28` `M` `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
- `S28` `verify:` `test_registry_legal_grounding.py` -> `pass`
- `S29` `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `S29` `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S30` `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `S30` `verify:` `test_registry_legal_grounding.py` -> `pass`
- `S31` `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `S31` `verify:` `dev/corpus/tests/test_extraction_sidecar_freshness.py` -> `pass`
- `S32` `M` `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `S32` `verify:` `test_registry_legal_grounding.py` -> `pass`
- `S33` `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`
- `S33` `verify:` `uv run --no-sync pytest -o addopts='' src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py::test_every_committed_normative_legal_reference_satisfies_provenance_contract -q`
- `S34` `M` `src/cadrumo/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`
- `S34` `verify:` `uv run --no-sync python -`

## Notes

- `S34` The selected test imports but does not use the currently absent shared `_registry_schema_support` helper. Its import symbol was supplied in memory solely for this focused run; the test's real `verify_source_file` and classifier paths were not substituted.
