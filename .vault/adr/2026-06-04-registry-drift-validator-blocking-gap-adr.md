---
tags:
  - '#adr'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-research]]'
  - '[[2026-06-04-registry-remaining-hardening-wireframe-audit]]'
  - '[[2026-06-04-registry-generic-fragmentation-contract-audit]]'
---

# `registry-drift-validator-blocking-gap` adr: `Registry drift validator blocking gap ADR` | (**status:** `accepted`)

## Problem Statement

The registry hardening roadmap identified drift validators as the next
substrate after generic fragment support. One validator class still had an
advisory-only path where unreviewed semantic-role typo twins should instead
block registry loading.

## Considerations

- Preserve committed corpus behavior when the corpus is clean.
- Keep diagnostic warning surfaces for focused callers where they remain
  useful.
- Promote only the selected typo-twin gap to a registry-scope failure.

## Constraints

This ADR does not authorize schema semantics changes, legal registry edits, or
broad validator redesign. It is bounded by the parent remaining-hardening and
fragmentation-contract audits and by the existing registry validation API.

## Implementation

Add a failure-producing path for semantic-role typo twins and route that path
through registry-scope validation, while retaining the diagnostic warning path
for focused callers. Prove blocking behavior with a mutation regression and
prove current corpus safety with committed-registry validation.

## Rationale

Registry load should fail when a semantic role appears to be an unreviewed
typo twin, because allowing that drift through as advisory-only can brief
developers and downstream calculation work from ambiguous registry semantics.

## Consequences

The selected drift class is now fail-closed at registry scope. The tradeoff is
that future intentional singleton role additions need deliberate review rather
than relying on advisory diagnostics.

## Codification candidates

None. Existing registry validation and source-hygiene rules cover the durable
constraint.
