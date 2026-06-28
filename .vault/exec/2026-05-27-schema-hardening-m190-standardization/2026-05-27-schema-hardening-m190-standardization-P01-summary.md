---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` `P01` summary

Completed the M190 generic directory-fragment standardization slice.

- Modified: `src/aeat/_data/registry/aeat/modelos/190`
- Created: `.vault/audit/2026-05-27-schema-hardening-m190-standardization-inventory.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m190-standardization-review.md`

## Description

Modelo 190 now uses the generic `manifest.toml` plus
`revisions/2024-y-siguientes` fragment-directory layout. The split removed the
largest remaining single-file modelo without changing registry schema
semantics, loader behavior, validation behavior, or model-specific application
logic.

The resulting M190 source has 15 TOML fragments and a largest-fragment size of
285 lines. The remaining single-file normalization queue now starts with M115,
M720, and M390.

## Tests

Verification passed:

- M190 focused loader/registry slice: 27 passed.
- Broader M190 registry integrity slice: 134 passed.
- Vault plan/frontmatter/body-link checks passed for this plan.
