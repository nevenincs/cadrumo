---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m184-standardization-review-audit]]'
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
---
# `schema-hardening` `m193-standardization` plan

### Phase `P01` - M193 single-revision directory standardization

Normalize Modelo 193 from the largest remaining single-file modelo into the generic directory/fragments substrate without changing schema semantics, loader behavior, or per-modelo definitions.

- [x] `P01.S01` - Inventory M193 single-file section boundaries and record the mechanical directory split strategy before editing registry data; `.vault/audit`.
- [x] `P01.S02` - Mechanically split M193 into `manifest.toml` and `revisions/2024-y-siguientes` fragments using the existing generic loader layout; `src/aeat/_data/registry/aeat/modelos/193`.
- [x] `P01.S03` - Verify M193 directory loading, registry integrity, annual-summary relation behavior, detail-record row behavior, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [x] `P01.S04` - Record review outcome, standardization baseline, and the next single-file normalization edge; `.vault/exec`.
