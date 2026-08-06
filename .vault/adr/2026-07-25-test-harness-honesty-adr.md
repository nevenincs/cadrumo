---
tags:
  - '#adr'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:6f1902c1d34da518de137d7f129d9bcd58d642264f40a4990a884128fc9f8c08'
related:
  - "[[2026-07-25-test-harness-honesty-false-green-gates-audit]]"
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# `test-harness-honesty` adr: `A gate must prove it discriminates: positive controls on every scanning gate` | (**status:** `accepted`)

## Problem Statement

## Considerations

## Considered options

## Constraints

## Implementation

## Rationale

## Consequences

## Context

Two gates were found green-while-vacuous on the same day. The bare-literal survivor scan compiled a pattern from a raw string carrying a doubled backslash, so it required a literal backslash before the token and could never match a real string literal; it had passed since it was written while four live sites went uncaught. The documentation claims gate scanned a corpus that yielded zero claims, hit an early return, and never reached its assertion; it was green because it matched nothing.

Both share one shape: a gate whose passing result is indistinguishable from a gate that is not measuring. Neither could be caught by reading the assertion, because the assertion was correct in both cases. What was missing was any evidence that the instrument still worked.

The decision is that a gate which scans for a pattern must carry a positive control: a known-good input the pattern MUST match and a near-miss it MUST NOT, asserted directly against the compiled pattern rather than through the scan. A gate that scans a corpus must additionally assert that corpus is non-empty, because an empty scan passes silently. Where a gate grants an escape to a site, the escape carries a test that fails when the construct justifying it disappears, so an escape cannot outlive its own reason.

This is the same principle the project already applies to calculation tests, where a test that would pass against a wrong formula is worthless. A gate that would pass against a broken instrument is worthless for the same reason. The prior duplication-measurement incident, where the reporting instrument became the duplication it measured and rendered zero clones green while 65 existed, is the same failure a generation earlier.
