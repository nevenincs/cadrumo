---
tags:
  - '#adr'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-m100-2025-row-width-research]]'
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
  - '[[2026-06-04-registry-m100-row-width-deferrals-adr]]'
---

# `registry-m100-2025-row-width` adr: `Registry M100 2025 row-width ADR` | (**status:** `accepted`)

## Problem Statement

The M100 deferral slice closed the immediate 530-character baseline pressure
but left four clean 2025 rows above the preferred 520-character reviewability
headroom target. A follow-on decision is needed to authorize only safe
formatting of those rows.

## Considerations

- Preserve the legal and source reference values exactly.
- Keep the scope to clean M100 2025 `legal_refs` row wrapping.
- Tighten the baseline only if the post-format corpus supports it.

## Constraints

This ADR does not authorize legal-reference edits, source-reference edits,
schema changes, loader changes, or unrelated dirty-fragment cleanup. It relies
on the completed M100 row-width deferral plan as the stable parent context.

## Implementation

Wrap the remaining clean M100 2025 legal-reference rows, rerun registry
reviewability and corpus gates, and lower the row-width baseline only when the
loaded registry corpus proves the tighter limit.

## Rationale

Keeping the work as a separate follow-on avoids mixing formatting headroom with
the completed M100 deferral closure and prevents stale plan state from briefing
future agents that the prior deferral plan is still open.

## Consequences

The registry keeps more reviewability headroom without changing registry
semantics. Future long-row pressure can be evaluated against the tighter
baseline.

## Codification candidates

None. Existing registry reviewability and source-hygiene rules cover the
durable constraint.
