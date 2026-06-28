---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---



# `schema-hardening-coti` `P02.S04`

Marked the six reviewed quoted-fund `coti` singleton rows explicitly.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2214-2227.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2215-2228.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2216-2229.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2217-2230.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2218-2231.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2221-2234.toml`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P02-S04.md`

## Description

The six warning-exposed `gp_fondos_coti` rows now carry explicit
`intentional_singleton` metadata with source-grounded reasons.

## Tests

Covered by P03.S06 gate results.
