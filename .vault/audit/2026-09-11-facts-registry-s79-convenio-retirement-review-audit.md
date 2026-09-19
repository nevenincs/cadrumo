---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:e8718c2e97ad2fba9bc99efb724a14ba445d9743a6b97cf03fcd7e4e0d94bace'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S79 convenio adapter retirement review`

## Scope

Independent review of W04.P15.S79 against the approved plan, the accepted Convenio decision and research, the adapted-family-normalization reference, and the pre-change treaty rows at `HEAD`.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW findings. The direct fact preserves all 21 pre-change rows: country and income selectors, validity windows, override kind and typed value, legal-reference sequence and anchor, source identity and required citation text. The established `ConvenioAuthority` is projected from that fact and legal authority, retaining each country document identity without restoring a second authoring surface.

The raw provider registration, raw directory ownership, raw reader, compiler, cache fingerprint path, and adapter-only tests are absent. Repository census found no legacy raw-provider symbols or raw-tree reader; remaining `treaties` usages are the retained runtime catalogue mapping and negative retirement assertions.

## Recommendations

Final verdict: CLEAR. The S79 implementation satisfies canonical one-way fact authority, evidence/applicability parity, and no-compatibility retirement requirements. Focused review validation passed: 23 tests and Ruff; the independent `HEAD` parity check found 21 expected rows, 21 current variants, with no missing or unexpected semantic row.
