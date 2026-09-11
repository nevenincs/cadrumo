---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:4693432e4db1953eb659f7e3d228255f63efa56eadcbbee55b47ef0c2c678392'
step_id: 'S76'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Repair Article 101 excerpt filenames and source references so provision-tier evidence is verifiable before the cross-domain authority proof

## Scope

- `src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/_data/registry/aeat/facts`

## Changes

- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20150101.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20150101.xml`
- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20150712.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20150712.xml`
- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20180705.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20180705.xml`
- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20181229.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20181229.xml`
- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20210101.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20210101.xml`
- `R` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20230101.xml` -> `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-101-redaction-20230101.xml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `A` `.vault/audit/2026-09-10-facts-registry-s76-article-101-provision-path-review-audit.md`
- `verify:` `uv run python -c "... verify_source_file(...) ..."` -> `pass`
- `verify:` `uv run pytest -q dev/registry/tests/test_catalogue_verification_catalogues.py::test_committed_registry_tree_has_coherent_shared_catalogues` -> `pass`
