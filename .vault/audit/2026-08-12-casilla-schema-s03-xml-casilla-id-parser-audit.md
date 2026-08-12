---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6d6882d8c25b59dddb4b9f8dde2853d9999f67be6149498d3fce4c55629788e2'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
---
# `casilla-schema` audit: `S03 XML Casilla Identifier Parser Audit`

## Scope

Audited the XML dictionary casilla-identifier parser against the bundled Modelo 100 dictionaries for 2024 and 2025 and the accepted canonical-derivations boundary. The parser must preserve official identifier spelling while admitting only the documented numeric and one-letter annex conventions.

## Findings

### xml-casilla-identifier-grammar | medium | digits-only parsing hid official annex identifiers

The former parser rejected the official one-letter identifier `A`, preventing complete Modelo 100 XML declaration classification. The corrected parser admits only decimal digit strings or one uppercase ASCII letter, preserves the exact source spelling, and continues to reject placeholders, lowercase identifiers, multi-letter values, and mixed labels.

### real-source-boundary | low | bundled 2024 and 2025 rows prove both admitted forms

Tests read the bundled official dictionaries and prove `TITA` resolves to `0001` while `VHADQ` resolves to `A` in both supported years. Formal review approved the corrected dependency chain with zero unresolved critical, high, or medium findings.

## Recommendations

Keep the parser grammar closed and source-preserving. Any additional identifier form must be grounded in an exact official dictionary row and added explicitly; normalization or permissive fallback remains forbidden.
