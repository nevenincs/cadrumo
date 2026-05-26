---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-26'
tier: L2
related:
  - '[[2026-05-22-schema-hardening-plan]]'
  - '[[2026-05-26-schema-hardening-open-edge-closeout]]'
  - '[[2026-05-26-schema-hardening-code-review]]'
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

# `schema-hardening` `m131-fragmentation` plan

### Phase `P01` - M131 generic revision fragmentation

Split Modelo 131 from large per-revision TOML files into generic revision fragment directories, using the loader-supported layout already proven by M100, M200, M303, M111, and M349.

- [x] `P01.S01` - Inventory M131 revision section boundaries and record the mechanical split strategy before touching registry data; `.vault/audit`.
- [ ] `P01.S02` - Mechanically split M131 revision files into revision-directory fragments without changing schema semantics or per-modelo loader behavior; `src/aeat/_data/registry/aeat/modelos/131`.
- [ ] `P01.S03` - Verify M131 fragment loading, registry integrity, and reviewability gates after the split; `src/aeat/domain/calculations/registry tests`.
- [ ] `P01.S04` - Record review outcome, file-size baseline, and next fragmentation edge; `.vault/exec`.
