---
tags:
  - '#adr'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-research]]'
  - "[[2026-06-04-registry-row-width-pressure-audit]]"
  - "[[2026-06-04-registry-row-width-pressure-plan]]"
---

# `registry-m100-row-width-deferrals` adr: `Registry M100 row-width deferrals ADR` | (**status:** `accepted`)

## Problem Statement

The registry row-width pressure work closed the general reviewability
regression but intentionally left a small M100-specific deferral set. The
remaining rows need a separate decision because they sit in legally sensitive
registry fragments where formatting work must preserve source references,
legal references, loader behavior, and committed registry equality.

## Considerations

- Keep the row-width work scoped to M100 deferrals that were already
  identified by the parent pressure pass.
- Preserve registry semantics exactly; formatting and TOML table shape are
  the only authorized changes.
- Keep reviewability baselines honest rather than raising module or TOML row
  limits to hide the pressure.

## Constraints

The parent row-width pressure feature is stable enough to use as the
authorizing context because its plan and audit already narrowed the remaining
work to M100. This ADR does not authorize source-reference edits,
legal-reference edits, schema changes, loader changes, or unrelated dirty
M100 completeness-fragment cleanup.

## Implementation

The M100 deferral slice formats the remaining long `legal_refs` arrays and
converts the identified 2020 inline constraints row into an equivalent nested
TOML table. Verification remains anchored on registry reviewability, directory
loader behavior, committed registry consistency, and plan checks.

## Rationale

Separating this work from the completed row-width pressure plan keeps the
review boundary clear. M100 carries dense legal-reference rows, so the safest
decision is to authorize only structure-preserving formatting and to leave the
existing baseline pressure visible until the deferrals are genuinely closed.

## Consequences

The plan can proceed without broadening the parent registry pressure scope.
The tradeoff is that M100 row-width debt remains visible until each deferred
row is verified by the registry gates.

## Codification candidates

None. This is a scoped follow-on decision covered by existing registry
reviewability and source-hygiene rules.
