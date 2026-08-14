---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:6fed7b5385cb02738460dee9c8c44e42c25d17acd5f4dddc12bf8a042cc9abb5'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S67 M303 2023 semantic map review`

## Scope

Review S67 against the accepted generator-authority decision, the S63 projection declarations, and the S86 static inspection boundary. Inspect the authored map and profile, real-source census, static compiler and provenance tests, canonical loader path, all relevant consumers, the explicit closer-type narrowing, and the boundary excluding S16/S91 filing-instance proof.

## Findings

No critical, high, medium, or low findings.

The source-pinned census proves 406 anchors as 393 fixed plus thirteen DP30300 prefix anchors, the declared semantic class totals, and exactly 134 post-S63 simplified-regime projections. Manual review of every distinct semantic-home pattern found no misassignment. The profile has exactly three reviewed singleton rules and covers every absent official wire fact. Static generation uses `RegistryRevisionInspection`, the official source and canonical loaders; no filing `RegistrySnapshot`, raw registry-loader bypass, instance payload, product identity value, digest, or total crosses the generator boundary.

The explicit `RecordDesignIntermediateRelativeSuffixMarker` narrowing makes the source-proved DP30300 closer shape visible to strict static analysis. Focused and broader real-behavior suites pass, Ruff is clean, and basedpyright reports zero errors.

## Recommendations

Accept S67. Keep filing-instance occurrence and emitted-byte proof in S16/S91; do not expand this static map-authoring closure into that downstream scope.
