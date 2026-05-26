---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m190-standardization-review]]'
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

# `schema-hardening` `m115-standardization` plan

### Phase `P01` - M115 single-revision directory standardization

Normalize Modelo 115 from the largest remaining single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M115 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [x] `P01.S02` - Mechanically split M115 into `manifest.toml` and `revisions/2019-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/115`.
- [x] `P01.S03` - Verify M115 directory loading, registry integrity, export layout behavior, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [ ] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
