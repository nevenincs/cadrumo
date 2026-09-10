---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:0c07f74000c61bb285f601dd5b7da5a5b4d77d58fdee6081703da9bc410946ec'
step_id: 'S73'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Capture hash-pinned BOE article 31 and transitional-provision redactions and author source-cited temporal objective-estimation exclusion facts under the governed authority

## Scope

- `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`

## Changes

- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-31-redaction-20070101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-31-redaction-20121031.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-art-31-redaction-20160101.xml`
- `A` `src/cadrumo/_data/corpus/normatives/html/boe-a-2006-20764-dt-32-redaction-20160101.xml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0022-lirpf-dt-32-eo-exclusion-rendimientos-conjunto.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0023-lirpf-dt-32-eo-exclusion-rendimientos-factura.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0024-lirpf-art-31-eo-exclusion-rendimientos-agricolas-ganaderos-forestales.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0025-lirpf-dt-32-eo-exclusion-compras.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_article31_dt32_objective_exclusion_authored_facts.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_article31_dt32_objective_exclusion_authored_facts.py` -> `pass`
