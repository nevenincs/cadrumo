---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e381cb34a4e54a2ab8c5231bea959242944b00d7811b3cbc8ee1e603a4728096'
step_id: 'S16'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Prove deterministic double generation and repository check mode on real bundled sources

## Scope

- `dev/registry/tests/`

## Description

- Ground the check surface, governing decision, and current plan through bounded semantic discovery.
- Exercise the current isolated check and drift-refusal tests against the bundled authority boundary.
- Audit the proposed real-source determinism proof with an independent Luna reviewer.

## Outcome

S16 remains open. The review established that no current exact-anchor semantic map and generated repository target exists for a parser-backed Modelo 200 generation. A synthetic intermediate cannot prove the required real-source or repository-check behavior and was not retained.

## Notes

Focused existing check tests passed before the review finding. The blocker is a plan dependency contradiction, not a transient Git or environment failure: W04 semantic-map and generated-target work must provide the authoritative inputs before this S16 claim can be tested honestly.
