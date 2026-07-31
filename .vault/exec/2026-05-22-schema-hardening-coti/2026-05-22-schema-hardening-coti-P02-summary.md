---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-07-17'
body_hash: 'sha256:5721689128614c027057be7cbb5882ddd7f3903ae0bb44e69793d679b50c539a'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---

# `schema-hardening-coti` `P02` summary

Completed the narrow `coti` optional-token implementation.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2214-2227.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2215-2228.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2216-2229.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2217-2230.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2218-2231.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2221-2234.toml`

## Description

The implementation removes `coti` from global optional stripping and replaces
the hidden warning suppression with explicit source-backed singleton metadata.

## Tests

Covered by P03.S06 gate results.
