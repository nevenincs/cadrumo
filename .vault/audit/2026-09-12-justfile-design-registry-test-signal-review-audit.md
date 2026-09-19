---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:be368b9d7f6b338f0104dfbcbdc705493c3569bccd98613418d443be9d790019'
related:
  - "[[2026-09-11-justfile-design-plan]]"
  - "[[2026-09-11-justfile-design-adr]]"
  - "[[2026-09-11-registry-test-signal-reference]]"
---

# `justfile-design` audit: `registry test signal review`

## Scope

Reviewed the `test-registry` orchestration, lane transport, summary reducer, detector tests, exact artifact-backed authority load path, and canonical registry test-population ownership against the accepted command taxonomy and registry authority boundary.

## Findings

### summaryless-collection-classification | medium | Collection preflight failures initially read as generic tool failures

The first implementation failed closed and retained the root cause, but a collection preflight that ended before pytest emitted its terminal summary was classified as a tool failure. The follow-up added explicit validated lane-kind metadata. Summaryless collection failures now report `collection_failure` with phase `collection`, while artifact-load failures remain `tool_failure` with phase `tool`. A planted syntax failure and the live in-flight registry failure both exercise the distinction. Resolved.

### fail-closed-signal | low | Expected lanes cannot disappear behind a zero child exit

Missing, failed, and preflight-blocked expected lanes now force a non-zero result. Both preflights run before the granular suffix; if either fails, every granular lane emits a bounded blocked event rather than running derivative tests.

### population-ownership | low | Registry tooling populations are enrolled without duplicate canonical ownership

The analysis, compiler, and pipeline test roots are present in collection and execution scope. Test-, file-, and directory-level reachability checks pass, including canonical uniqueness.

### review-verdict | low | Independent review found no critical or high issues

Focused reducer and transport tests, registry population ownership, formatting, lint, recipe parsing, and the live failure path were verified. Output remains bounded and the exact runtime-load preflight delegates to the existing artifact-backed authority owner.

## Recommendations

Resolve the separate in-flight `Modelo` and `TaxDomain` schema-generation failures through the registry campaign. Keep collection and artifact loading as prerequisite facts; do not weaken or bypass either lane to make downstream tests run.
