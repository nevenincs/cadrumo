---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:d3104d08b236a779d0900c9b2b7e8635935d6adf412787fa3b1ad756b69b950b'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` reference: objective-estimation publication boundary

## Summary

`_objective_estimation_exclusion_advisory_findings` consumes four typed scalar governed facts at a filing-period coordinate derived from the work unit's filing year. The consumer emits only the resolved fact identifier and its legal and source provenance. It has no legal-parameter loader, raw TOML read, rate literal, or consumer-side fallback.

The four legal values are one-fact-per-file declarations with dated variants, legal references, source references, required citations, reviewed state, and decimal EUR payloads. DT 32 values govern the 2016â€“2024 variants; the three transitional facts select Article 31 sources and values from 2025; the agricultural threshold remains its separately grounded Article 31 fact.

Runtime authority is intentionally a separate publication boundary. `bundled_authority` reads and verifies only `registry/authority/authority.json`; it never recompiles authoring data. Development validation instead uses `compiled_bundled_authority`. The local tree does not contain the signed artifact, so runtime-focused source tests correctly refuse before the consumer is reached.

## Completion evidence required

Before the plan step closes, publish the signed artifact through the owning release flow and run the focused objective-estimation advisory and revision-verification integration tests against it. The receipt must prove the four fact resolutions at both the 2024 and 2025 filing coordinates, including variant cutover, legal/source provenance, and authority identity. A source-compilation fallback would contradict the accepted publication boundary and is not an acceptable substitute.
