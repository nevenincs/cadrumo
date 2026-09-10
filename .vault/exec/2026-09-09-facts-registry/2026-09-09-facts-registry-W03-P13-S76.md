---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:485a31e0330a819114b3aa87130391d5ca4bf0e2bb607169e2f59372daec93ae'
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

## Notes

`uv run pytest dev/registry/tests/test_catalogue_verification_catalogues.py -q` had no terminal receipt under shared-host Python saturation. S76 remains open pending that broader proof.
