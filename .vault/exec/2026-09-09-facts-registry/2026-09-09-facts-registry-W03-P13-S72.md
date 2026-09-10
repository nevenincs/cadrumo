---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:96424868c9b6e841cfdb0f687bcb6e31ab60f4da19f57bd8bd78eea7e0787352'
step_id: 'S72'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
