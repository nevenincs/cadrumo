---
tags:
  - '#research'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3af689e5eeffc2f524311d04e031d9cad84e213b209a111f6e5bb4bf893dc3f9'
related:
  - '[[2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research]]'
---
# `registry-temporal-coverage` research: `corpus tier enforcement`

The original recommendation to mandate `corpus_tier` for normative citations is withdrawn. Follow-up corpus evidence shows that the field correctly classifies excerpt-versus-full-text, but cannot establish that the cited text is BOE-derived. The M037 paraphrase would pass as `provision_excerpt`; the decision therefore belongs to a derived file-provenance gate, with `corpus_tier` retained as its independent existing contract.

## Findings

### M037 exposed a provenance gap, not an omitted-tier gap

`orden-hac-1526-2024:art-1` resolves `#a1`; the legal dispositive-content validator only reads anchors matching `^modelo-\\d+$`, so it returns before testing this anchor (`src/cadrumo/domain/calculations/registry/legal.py:139-154`). `SourceReference.corpus_path` has no anchored reader (`src/cadrumo/domain/calculations/registry/schema_references.py:518-533`). These are distinct coverage limits, but neither explains whether the text came from BOE.

### A mandatory tier would accept the motivating file

`corpus_tier` records the whole-instrument versus provision-excerpt distinction. A `provision_excerpt` declaration for `orden-hac-1526-2024-art-1.html` would pass immediately because the `-art-` suffix is the verifier's accepted excerpt convention (`src/cadrumo/domain/calculations/registry/legal.py:182-220`). The provenance survey identifies this file among five hand-shaped normative files backing six legal citations, five with `legal_authority` evidence tier (`.vault/research/2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research.md`). Thus, changing optional to mandatory does not detect the stated defect.

### Completeness and provenance are independent authority properties

The existing two-valued contract remains useful and is checked when declared (`src/cadrumo/domain/calculations/registry/corpus_catalogue.py:80-123`; `src/cadrumo/domain/calculations/registry/legal.py:182-220`). It must not be overloaded with a third state: an author-declared status cannot prove the provenance of author-written text. The evidence-favoured alternative derives provenance once from each normative corpus file's bytes, then binds filing-grade evidence to that derived result. The related research records the measured attribution bands and the unresolved presumptive band.

### The stale coverage statement remains a documentation defect

`legal.py` says no committed `LegalReference` declares `corpus_tier`, although the registry contains 19 declarations (`src/cadrumo/domain/calculations/registry/legal.py:183-190`; `src/cadrumo/_data/registry/aeat/legal/irpf-impatriados.toml:84-374`; `src/cadrumo/_data/registry/aeat/legal/modelo-185.toml:14-34`; `src/cadrumo/_data/registry/aeat/legal/patrimonio.toml:323-494`). The equivalent statement for `SourceReference` remains accurate (`src/cadrumo/domain/calculations/registry/corpus_catalogue.py:81-87`).

## Sources

- `src/cadrumo/domain/calculations/registry/legal.py:139-220`
- `src/cadrumo/domain/calculations/registry/schema_references.py:518-533`
- `src/cadrumo/domain/calculations/registry/corpus_catalogue.py:80-123`
- `src/cadrumo/_data/registry/aeat/legal/irpf-impatriados.toml:84-374`
- `src/cadrumo/_data/registry/aeat/legal/modelo-185.toml:14-34`
- `src/cadrumo/_data/registry/aeat/legal/patrimonio.toml:323-494`
- `.vault/research/2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research.md`
