---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:91e82be8bd22d03ad8694c498846ff512e3cc08e3c52548eb7eb53be46af40af'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# `sociedades-manual-coverage` ledger

## Changes

- `S01` `A` `src/cadrumo/_data/registry/aeat/legal/sociedades-annual-manual-coverage.toml`
- `S01` `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/loader.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_coverage.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_applicability_registry_cutover.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_loader_directory_mode.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_loader_cache_isolation.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_mutable_tree_fingerprint_invalidation.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_binding_readiness.py`
- `S01` `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py -q --disable-warnings --maxfail=1` -> `pass`
- `S02` `M` `src/cadrumo/application/registry/corpus.py`
- `S02` `M` `src/cadrumo/application/registry/tests/test_corpus.py`
- `S02` `verify:` `uv run pytest -n 0 src/cadrumo/application/registry/tests/test_corpus.py::test_manuals_list_report_localizes_the_unpublished_acquisition_condition -q --disable-warnings --maxfail=1` -> `pass`
- `S03` `M` `src/cadrumo/entrypoints/cli/_registry_corpus.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/_registry_corpus_payloads.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py`
- `S03` `M` `src/cadrumo/core/redaction/rules.py`
- `S03` `verify:` `uv run pytest -n 0 -m "hex_entrypoint and integration" src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py::test_manuals_list_emits_json_payload -q --disable-warnings --maxfail=1` -> `pass`
- `S04` `M` `src/cadrumo/locales/ca/application.yml`
- `S04` `M` `src/cadrumo/locales/ca/cli.yml`
- `S04` `M` `src/cadrumo/locales/en/application.yml`
- `S04` `M` `src/cadrumo/locales/en/cli.yml`
- `S04` `M` `src/cadrumo/locales/es/application.yml`
- `S04` `M` `src/cadrumo/locales/es/cli.yml`
- `S04` `M` `src/cadrumo/locales/hu/application.yml`
- `S04` `M` `src/cadrumo/locales/hu/cli.yml`
- `S04` `verify:` `uv run pytest -n 0 src/cadrumo/application/registry/tests/test_corpus.py::test_manuals_list_report_localizes_the_unpublished_acquisition_condition -q --disable-warnings --maxfail=1` -> `pass`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/manifest.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.md`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/chapters.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/manual.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/manifest.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.md`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/chapters.json`
- `S05` `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/manual.json`
- `S05` `A` `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2022/source.pdf.corpus_text.json`
- `S05` `A` `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2023/source.pdf.corpus_text.json`
- `S05` `verify:` `uv run pytest dev/corpus/tests/test_extraction_sidecar_freshness.py::test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256 -q` -> `pass`
- `S06` `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `S06` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py -q` -> `pass`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes`
- `S07` `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py`
- `S07` `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_revision_fragments_never_cite_another_years_annual_manual src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_validates_with_deadline_and_schedule_catalogue_refs -q` -> `pass`
- `S08` `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `S08` `verify:` `uv run pytest dev/corpus/tests/test_extraction_sidecar_freshness.py -k "supported_tax_manual_matrix or manual_pdf_corpus_text_sidecars_exist or every_corpus_pdf_has_a_corpus_text_sidecar"` -> `pass`
- `S09` `M` `docs/cli/app/registry.rst`
- `S09` `M` `docs/_static/cli-tree.json`
- `S09` `M` `dev/docs/tests/test_cli_tree.py`
- `S09` `verify:` `uv run pytest dev/docs/tests/test_cli_reference_pages_are_not_stubs.py dev/docs/tests/test_cli_anchor_parity.py` -> `pass`
- `S09` `verify:` `uv run pytest dev/docs/tests/test_cli_tree.py -k "sociedades_manual_list or projection_covers_every_collected_path or write_cli_tree_emits_default_static_path" dev/docs/tests/test_sequence_build_gate.py` -> `pass`
- `S10` `T`
- `S10` `verify:` `uv run python -c "... ZipFile(...).namelist() ..."` -> `pass`
- `S10` `verify:` `uv run pytest dev/packaging/tests/test_cadrumo_data_distribution.py` -> `fail`

## Notes

- `S10` The real source-tree wheel contains the 2022 and 2023 Sociedades PDFs. The
- `S10` tracked-artifact parity gate correctly refuses to pass until those newly
- `S10` acquired corpus inputs are staged or committed; no index mutation was
- `S10` authorised.
