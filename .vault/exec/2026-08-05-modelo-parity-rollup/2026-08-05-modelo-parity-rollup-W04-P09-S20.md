---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:32ac83d8294942d9222f74c416ecf05477b7d0f17f1806b5164c0ce9a9065dcb'
step_id: 'S20'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Modelo parity rollup S20 failure tests for formula wiring

## Description

- Exercise the reverse formula invariant through real registry objects.
- Assert that formula-target and casilla-kind mismatches fail validation.
- Assert that both sides of a producer declaration carry the same formula identity.

## Outcome

The real failure-test surface passed 8 tests. The suite demonstrates that the reverse invariant can fail when a target is manual, when the casilla lacks the back-reference, when a computed casilla lacks a producer, when a noncomputed casilla carries a formula declaration, or when a formula target is duplicated.

## Notes

These are structural tests over the bundled registry and validator behavior; they do not infer a legal formula for a deferred revision.
