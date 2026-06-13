---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m322-standardization-plan]]'
---



# `schema-hardening-m322-standardization` `P01` summary

Modelo 322 was standardized from root-level single-file TOML into the generic
directory/fragments registry layout.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m322-standardization-plan.md`
- Deleted: `src/aeat/_data/registry/aeat/modelos/322.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/322/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/322/revisions/2008-y-siguientes/revision.toml`
- Created: 12 ordered revision section fragments under `src/aeat/_data/registry/aeat/modelos/322/revisions/2008-y-siguientes`
- Created: `.vault/audit/2026-05-27-schema-hardening-m322-standardization-inventory.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m322-standardization-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m322-standardization`

## Description

The source file was split mechanically. The generated fragment stream matched
the committed `322.toml` source exactly before the stale single-file sibling
was removed. No loader, schema, validator, or Modelo 322 semantic content was
changed.

The final review baseline is:

- Modelo 322 fragment count: 14.
- Largest Modelo 322 fragment: 104 lines.
- Largest remaining root-level single-file modelo: `353.toml` at 569 lines.
- Next recommended slice: Modelo 353 standardization.

## Tests

- Focused M322 and directory-mode gate: 34 passed.
- Broader registry gate covering committed registry, referential integrity, and
  IVA ledger aggregation binding behavior: 143 passed.
- Vault plan check: passed.
- External code review: no blocking findings.
