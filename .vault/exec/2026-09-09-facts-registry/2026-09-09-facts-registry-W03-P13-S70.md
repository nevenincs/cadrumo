---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c556125775215ed510844c221b8f9906a813586fb0da73be0573a734d4a2a3ca'
step_id: 'S70'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Capture and author the bounded administrator-retention fact slice from BOE redactions

## Scope

- `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts`

## Changes

- `M` `dev/corpus/fetch_boe_normative.py`
- `M` `dev/tests/test_fetch_boe_article.py`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20150101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20150712.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20180705.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20181229.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20210101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-a101-redaction-20230101.xml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0001-lirpf-art-101-retencion-administrador-general.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0002-lirpf-art-101-retencion-administrador-reducida.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0003-lirpf-art-101-retencion-administrador-incn-umbral-eur.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_administrator_retention_authored_facts.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py`
- `A` `.vault/audit/2026-09-10-facts-registry-s70-administrator-retention-review-audit.md`
- `verify:` `uv run --no-sync pytest dev/tests/test_fetch_boe_article.py src/cadrumo/domain/calculations/registry/facts/tests/test_administrator_retention_authored_facts.py src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py dev/registry/tests/test_facts_wave2_provider_handoff.py` -> `pass`
