---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` `P01` summary

Completed the M390 generic directory-fragment standardization slice.

- Modified: `src/aeat/_data/registry/aeat/modelos/390`
- Created: `.vault/audit/2026-05-27-schema-hardening-m390-standardization-inventory.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m390-standardization-review.md`

## Description

Modelo 390 now uses the generic `manifest.toml` plus
`revisions/2010-y-siguientes` fragment-directory layout. The split removed the
largest remaining single-file modelo without changing registry schema
semantics, loader behavior, validation behavior, IVA annual-summary behavior,
or model-specific application logic.

The resulting M390 source has 15 TOML fragments and a largest-fragment size of
182 lines. The remaining single-file normalization queue now starts with M322
and M353.

## Tests

Verification passed:

- M390 focused loader/registry slice: 35 passed.
- Broader M390 registry/application/annual-IVA slice: 129 passed after the
  stale M303/M390 filing test inputs were corrected in concurrent commit
  `a5a01f573`.
- Vault plan/frontmatter/body-link checks passed for this plan.
