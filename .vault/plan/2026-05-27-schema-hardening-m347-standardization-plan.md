---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-m193-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m193-standardization-P01-S04]]'
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

# `schema-hardening` `m347-standardization` plan

### Phase `P01` - M347 single-revision directory standardization

Normalize Modelo 347 from the largest remaining root-level single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M347 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [ ] `P01.S02` - Mechanically split M347 into `manifest.toml` and `revisions/2008-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/347`.
- [ ] `P01.S03` - Verify M347 directory loading, registry validity, schedule/deadline behavior, extraction profile parsing, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [ ] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
