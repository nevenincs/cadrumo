---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b33f5fcb6fa14fc620fe0863751cf2490fcad7d855da634b2c6ba3d97bde1b75'
step_id: 'S71'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Capture hash-pinned BOE articles 109 and 110 redactions, author source-cited temporal selectors by legal applicability, and rewire Modelo 131 to its form-specific authority

## Scope

- `dev/corpus and src/cadrumo/_data/corpus/normatives/html and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/calculations/registry/facts/legal_parameters.py and src/cadrumo/application/aggregation`

## Changes

- `R` `src/cadrumo/_data/registry/aeat/facts/0016-rirpf-art-110-selector-m036-pago-fraccionado-agrario-objetiva.toml` -> `src/cadrumo/_data/registry/aeat/facts/0016-rirpf-art-110-selector-m036-pago-fraccionado-agrarias-pesqueras.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0017-modelo-131-selector-m036-volumen-ingresos-agrario.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `M` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `M` `src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_article109_110_activity_selector_authored_facts.py`
- `A` `.vault/audit/2026-09-10-facts-registry-s71-repair-review-audit.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/facts/tests/test_article109_110_activity_selector_authored_facts.py` -> `pass`
