---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:318841c4044d72f317a53779701c74286d7c3df330a7c55e0b45765d5baf47d7'
step_id: 'S74'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Capture the official M036 activity-code mapping, author source-cited article-95 activity-selector facts, and remove their legacy adapter definitions

## Scope

- `dev/corpus and src/cadrumo/_data/corpus and src/cadrumo/_data/registry/aeat/facts and src/cadrumo/_data/registry/aeat/legal and src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/facts/0010-rirpf-art-95-selector-m036-profesionales.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0011-rirpf-art-95-selector-m036-agricolas-ganaderas.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0012-rirpf-art-95-selector-m036-forestales.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0013-rirpf-art-95-selector-m036-ganaderas-engorde-porcino-avicultura.toml`
- `M` `src/cadrumo/_data/registry/aeat/legal/statutory-constant-sources.toml`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_article95_activity_selector_authored_facts.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py`
- `A` `.vault/audit/2026-09-10-facts-registry-s74-activity-selector-review-audit.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/facts/tests/test_article95_activity_selector_authored_facts.py src/cadrumo/domain/calculations/registry/facts/tests/test_legal_parameter_provider.py src/cadrumo/domain/calculations/registry/facts/tests/test_loader.py` -> `pass`
