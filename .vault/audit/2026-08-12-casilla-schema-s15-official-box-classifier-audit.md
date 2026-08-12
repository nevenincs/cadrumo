---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b32f3e36a1615a9365d1cdf09162792da91b2477c3c2534533aa5a5182d46ad0'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
---
# `casilla-schema` audit: `S15 Official Box Classifier Audit`

## Scope

Audited `classify_official_boxes` as the sole public registry derivation for official-box declaration status across fixed-width export layouts, binding-derived layouts, and XML dictionaries. The audit included real M720, M349, and Modelo 100 2024/2025 registry/source behavior.

## Findings

### official-box-classifier-home | low | one public registry function derives all three statuses

The classifier derives binding fields before scanning casilla-keyed layouts, incorporates exact XML dictionary identifiers through the corrected S03 parser, and reports addressed, binding, or undefined without deciding producer ownership, value arrival, applicability, or completeness.

### xml-evidence-refusal | low | absent or invalid source evidence fails closed

XML classification requires the selected snapshot's grounded dictionary source. Missing source roots, unresolved paths, and malformed dictionary evidence refuse rather than silently classifying boxes as undefined. Formal review approved the S03/S14/S15 chain with zero unresolved critical, high, or medium findings.

## Recommendations

All consumers, including the S52 M303 census and S62 projection-declaration integration, must import this classifier. Re-unioning layout, binding, XML, or projection mechanisms elsewhere is a canonical-home regression.
