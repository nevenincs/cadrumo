---
tags:
  - '#reference'
  - '#registry-temporal-coverage'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f2114c55bbbdf33625b547e6dbf3a5ce43d6301aa2ae25665b7e1ab91e3542d3'
related:
  - "[[2026-08-31-registry-temporal-coverage-modelo-165-2023-layout-composite-research]]"
---
# `registry-temporal-coverage` reference: `Modelo 165 composite-layout implementation boundary`

## Purpose

Record the existing implementation boundary for the approved Modelo 165
2023--2025 derived-layout decision. This reference supports
`2026-08-31-registry-temporal-coverage-modelo-165-2023-layout-composite-research`
and the governing design-authority ADR; it does not decide the policy.

## Current implementation

`SourceReference` in `schema_references.py` represents exactly one physical,
hash-pinned corpus file. Catalogue verification checks that file's bytes and
content digest. Fixed-width export coverage reads only a layout's cited
`record_design` sources and strict-parses their binaries.

Modelo 165's `2023-2025` revision is applicability-only. Its historical test
pins that state; the complete `2016-2022` fragments and `aeat-dr-165-2016-2022`
source are the bounded predecessor. The later `aeat-dr-165-2026` stays in its
own interval and cannot establish historic geometry.

## Required shape

A derived Modelo 165 source needs an explicit, discriminated composite-layout
contract, rather than a second source identifier pointing at the 2016 PDF. The
contract must bind the base source identity, SHA-256 and bytes; the
provenance-only BOE amendment identity, SHA-256 and bytes; the exact modelo,
revision, and 2023--2025 window; and the closed delta: type 1 byte 184 becomes
`EMPRESA EMERGENTE`, type 1 filler becomes bytes 185--500, and type 2 remains
unchanged.

Validation must reject every other modelo, revision, window, input identity or
digest, direct raw-BOE layout selection, later-AEAT historical input, and
non-delta mutation. Fixed-width coverage must resolve the approved composite to
that synthesized geometry; ordinary parser coverage alone only sees the 2016
filler at byte 184.

## Implementation sites

- `schema_references.py` owns the typed source declaration.
- Catalogue and revision validation own scope, provenance, and input-digest
  refusals.
- `_validate_export_layout_coverage.py` owns the composite geometry check.
- `legal/modelo-165.toml` owns the amendment legal references and sources.
- Modelo 165's 2016 layout/casilla/construct/application-link/parity fragments
  are the direct data template for the 2023--2025 revision.
- `test_modelo_165_historical_layout_authority.py` owns exact-geometry and
  anti-backdating proof; adjacent source/catalogue tests own malformed-source
  refusals.

## Non-goals

This establishes no general BOE-to-layout promotion, successor inheritance, or
cross-modelo derivation mechanism. The raw BOE remains provenance-only; only
the narrowly identified composite may be selected as layout authority.
