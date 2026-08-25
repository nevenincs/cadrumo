---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7b8a0ed0753433a6829521af12c844760df9209dbd2e6482977540e9c4572725'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-temporal-coverage-W02-P05-S49]]'
---

# `registry-temporal-coverage` audit: `S49 Modelo 721 package review`

## Scope

Independent review of the S49 hunks in `0598215cab6` and `2442a30e17`, the temporal plan and S49 record, Modelo 721 legal and source evidence, revision trees, corpus PDFs, locale consumers, worklist, and mutation tests. Unrelated Modelo 347 hunks were excluded.

## Findings

### s49-boe-era-boundary | low | finite BOE Annex authority is correctly scoped

The 2023 HFP/886 and 2024 HAC/1504 PDFs match their declared hashes and byte counts. Each source is a BOE `form_spec`, applies only to its named exercise, and selects exactly one finite applicability-grade revision. The 2024 selector-expansion test proves the source window still rejects 2025.

### s49-nonclaim | low | unavailable AEAT SOAP/XML packages are not inferred

Neither revision claims a paired historic/current AEAT service package, positional record design, serializer, export layout, filing producer, or grade promotion. The absence of an exact historical 2023 SOAP/XML byte set stays an explicit non-claim rather than a substitute technical contract.

### s49-consumers | low | no stale era or locale consumer remains

The focused registry test proves the two revision IDs, finite selectors, 2025 refusal, source hashes, and empty export layouts. The revision locales are split to the same two identities, with no stale open era retained.

## Recommendations

Retain the BOE-only finite boundary. A future technical or output claim requires separately retrievable, exact, hash-pinned AEAT service evidence and its complete producer, map, and emitted-output proof chain.
