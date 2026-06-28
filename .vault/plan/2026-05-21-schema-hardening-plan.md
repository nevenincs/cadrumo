---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
tier: L2
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
  - '[[2026-05-20-schema-hardening-verification-ledger-audit]]'
  - '[[2026-05-21-schema-hardening-semantic-role-sidecar-audit]]'
  - '[[2026-05-18-schema-hardening-research]]'
---
# `schema-hardening` `semantic_role sidecar continuation` plan

### Phase `P01` - Modelo 200 correction-axis extraction design

This Phase designs the safe mechanical extraction boundary for Modelo 200 correction-table axes.

- [x] `P01.S01` - Define the Modelo 200 correction-axis metadata contract before any registry rewrite.; `src/aeat/domain/calculations/registry`.
- [x] `P01.S02` - Enumerate the Modelo 200 correction-axis base-role allowlist from official manual tables and current registry labels.; `.vault/audit`.
- [x] `P01.S03` - Enumerate the Modelo 200 label-versus-role mismatch records as an explicit review bucket.; `.vault/audit`.
- [x] `P01.S04` - Define regression checks that prevent legal base slugs from being collapsed during correction-axis extraction.; `src/aeat/domain/calculations/registry`.

### Phase `P03` - Modelo 200 policy-gated legal bases

This Phase records the legal and concept bases that extraction must preserve.

- [x] `P03.S05` - Document the keep-list for article, transitional-provision, provision, regime, event, SICAV, cooperative, port-authority, and entity-specific bases.; `.vault/audit`.
- [x] `P03.S06` - Define the review requirement for any future change to a keep-listed legal base slug.; `.vault/reference`.

### Phase `P02` - Modelo 100 family-local pilot

This Phase pilots carryforward-axis extraction only inside one manually grounded family.

- [x] `P02.S07` - Record the c_valenciana_autoconsumo family boundary from registry labels and the Renta 2025 manual.; `.vault/audit`.
- [x] `P02.S08` - Define the family-local axes for generated year and pending state.; `src/aeat/domain/calculations/registry`.
- [x] `P02.S09` - Define a guard that rejects cross-region normalization by repeated label alone.; `src/aeat/domain/calculations/registry`.

### Phase `P04` - Review gate

This Phase prevents implementation from running ahead of legal-source review.

- [x] `P04.S10` - Produce a reviewer checklist for every future semantic-role normalization slice.; `.vault/audit`.
- [x] `P04.S11` - Verify every implemented slice against the official manuals or registry source references named in its audit.; `.vault/audit`.
