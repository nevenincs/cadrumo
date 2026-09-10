---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:5d9750340eafd88707c814d6c777b41846ea6540ba94ad392c3d53b9c9b51f8c'
step_id: 'S72'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Capture hash-pinned BOE article 161 redactions and author source-cited temporal equivalence-surcharge facts under the governed authority

## Scope

- `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`

## Changes

- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-1992-28740-art-161-redaction-19930101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-1992-28740-art-161-redaction-19970101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-1992-28740-art-161-redaction-20120715.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2012-9364-art-23-redaction-20120715.xml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0018-liva-art-161-recargo-rate-general.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0019-liva-art-161-recargo-rate-reducido.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0020-liva-art-161-recargo-rate-super-reducido.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0021-liva-art-161-recargo-rate-tabaco.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_article161_recargo_authored_facts.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/facts/tests/test_article161_recargo_authored_facts.py` -> `pass`
