---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-26'
tier: L2
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
  - '[[2026-05-26-schema-hardening-m131-fragmentation-review]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `schema-hardening` `m130-standardization` plan

### Phase `P01` - M130 single-revision directory standardization

Normalize Modelo 130 from the largest remaining single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M130 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [ ] `P01.S02` - Mechanically split M130 into `manifest.toml` and `revisions/2019-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/130`.
- [ ] `P01.S03` - Verify M130 directory loading, registry integrity, single-file reduction, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [ ] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
