---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-m840-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m840-standardization-P01-S04]]'
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
---
# `schema-hardening` `m308-standardization` plan

### Phase `P01` - M308 final root-level single-file standardization

Normalize Modelo 308, the final remaining root-level single-file modelo,
into the generic directory/fragments substrate without changing schema
semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M308 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [x] `P01.S02` - Mechanically split M308 into `manifest.toml` and `revisions/2009-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/308`.
- [x] `P01.S03` - Verify M308 directory loading, registry validity, snapshot behavior, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [x] `P01.S04` - Record review outcome and confirm the root-level single-file modelo cleanup baseline; `.vault/exec`.
