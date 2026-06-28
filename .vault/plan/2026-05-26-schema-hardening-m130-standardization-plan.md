---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
tier: L2
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
  - '[[2026-05-26-schema-hardening-m131-fragmentation-review-audit]]'
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
---
# `schema-hardening` `m130-standardization` plan

### Phase `P01` - M130 single-revision directory standardization

Normalize Modelo 130 from the largest remaining single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M130 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [x] `P01.S02` - Mechanically split M130 into `manifest.toml` and `revisions/2019-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/130`.
- [x] `P01.S03` - Verify M130 directory loading, registry integrity, single-file reduction, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [x] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
