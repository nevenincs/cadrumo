---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a3e9a84575b34438db20b7d0cc6f01e4aa3e97b6faee2fa7af2d7b985d8806f2'
step_id: 'S68'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Capture hash-pinned BOE article 95 redactions and author source-cited temporal withholding-rate facts under the governed authority

## Scope

- `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`

## Changes

- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2007-6820-a95-redaction-20070401.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2007-6820-a95-redaction-20150101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2007-6820-a95-redaction-20150712.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2007-6820-a95-redaction-20181223.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2007-6820-a95-redaction-20230126.xml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0004-rirpf-art-95-retencion-profesionales-general.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0005-rirpf-art-95-retencion-profesionales-inicio.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0006-rirpf-art-95-retencion-agricolas-ganaderas-general.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0007-rirpf-art-95-retencion-ganaderas-engorde-porcino-avicultura.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0008-rirpf-art-95-retencion-forestales.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0009-rirpf-art-95-retencion-estimacion-objetiva.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_article95_retention_authored_facts.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py`
- `A` `.vault/audit/2026-09-10-facts-registry-s68-article95-retention-review-audit.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/facts/tests/test_article95_retention_authored_facts.py` -> `pass`
