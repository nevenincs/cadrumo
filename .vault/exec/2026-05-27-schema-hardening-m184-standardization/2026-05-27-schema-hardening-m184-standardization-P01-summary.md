---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---



# `schema-hardening-m184-standardization` `P01` summary

Modelo 184 was standardized from root-level single-file TOML into the generic
directory/fragments registry layout.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m184-standardization-plan.md`
- Deleted: `src/aeat/_data/registry/aeat/modelos/184.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/184/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes/revision.toml`
- Created: 11 ordered revision section fragments under `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes`
- Created: `.vault/audit/2026-05-27-schema-hardening-m184-standardization-inventory.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m184-standardization-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization`

## Description

The `7e3622864` source file split was mechanical: the generated fragment stream
matched the committed `184.toml` source exactly before the stale single-file
sibling was removed. No loader, schema, validator, or Modelo 184 semantic
content was changed by that split commit.

Current HEAD includes later cross-campaign commit `13f5e39db`, which changes
the M184 `declaracion_pdf` extraction profile. That work was preserved and is
tracked separately from the mechanical standardization baseline.

The final layout baseline is:

- Modelo 184 fragment count: 13.
- Largest Modelo 184 fragment: 95 lines.
- Largest remaining root-level single-file modelo: `193.toml` at 472 lines.
- Next recommended slice: Modelo 193 standardization.

## Tests

- Focused M184 and directory-mode gate: 32 passed.
- Broader registry/detail-record gate: 157 passed.
- Current HEAD rerun with parser-boundary coverage: 256 passed.
- Vault plan check: passed.
- External code review: flagged later cross-commit semantic drift; no stale
  sibling or loader-layout defect was found.
