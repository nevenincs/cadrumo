---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:9cb0af64ba066bf4849a48bae6d27837962c10dca779e50b9f99bb954df6def1'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# `registry-temporal-coverage` audit: `S48 Modelo 220 2025 scope review`

## Scope

Independent review of commit `62e45d6c596`, its S48 execution record, the temporal-coverage plan and decision evidence, the M220 revision, legal authority and source records, and the catalogue-verification gate.

## Findings

### s48-m220-scope | low | no temporal-authority defect found

The commit replaces M220's former open-ended identifier and directory with the canonical `2025` revision, constrains both validity and the `0A` selector to calendar 2025, and removes only the M220 publication-bound exception. The revision continues to declare `applicability` authority and an inspection-only, non-fileable boundary; it does not add a 2026 successor, export layout, or duplicate authority. The reviewed AEAT design is hash-pinned and ends on 2025-12-31, while the cited Orden's stated application boundary is the 2025 calendar year.

### s48-m220-scope | low | the hostile selector mutation is non-vacuous

The focused test loads the committed validated registry and first proves normal 2025 selection plus 2026 refusal. It then widens only an in-memory selector, proves that this would select the same revision in 2026, and invokes the same source-matrix predicate used by the supported-period gate. That predicate rejects the real M220 design source at the 2026 endpoint because its registered applicability ends in 2025; no mock, duplicate resolver, or substitute authority is involved.

## Recommendations

Retain the bounded revision and its shared-predicate mutation proof. A future 2026 M220 revision should be admitted only with separately hash-pinned era-matching design evidence and approving legal authority; it must not reopen this revision or restore its removed exception.
