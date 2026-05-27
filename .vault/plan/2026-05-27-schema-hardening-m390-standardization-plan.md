---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m720-standardization-review]]'
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

# `schema-hardening` `m390-standardization` plan

### Phase `P01` - M390 single-revision directory standardization

Normalize Modelo 390 from the largest remaining single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M390 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [ ] `P01.S02` - Mechanically split M390 into `manifest.toml` and `revisions/2010-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/390`.
- [ ] `P01.S03` - Verify M390 directory loading, registry integrity, IVA annual-summary behavior, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [ ] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
