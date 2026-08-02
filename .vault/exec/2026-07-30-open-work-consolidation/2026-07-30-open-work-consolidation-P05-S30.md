---
tags:
  - '#exec'
  - '#open-work-consolidation'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:a01389cad501472ab5da50fdef027c32cd553477ecd85c6b0a76a3f351d69d3e'
step_id: 'S30'
related:
  - "[[2026-07-30-open-work-consolidation-plan]]"
---

# Rerun the twelve semantic duplication probes and record the delta against the baseline they check for recurrence of, closing the residue of a row that was superseded rather than satisfied

## Scope

- `src/cadrumo/`
- `dev/audit/`

## Description
- Confirm the semantic index is trustworthy before believing any probe result.
- Rerun the probes whose original results were recorded as concrete misses.
- Rerun the removal check, where a hit would mean a retired concept had returned.
- Confirm each canonical owner with an exact search rather than resting on the semantic hit.

## Outcome

No duplication cluster recurred, and the original findings turn out to have been
artefacts of a broken instrument rather than real duplication.

The index was verified trustworthy first, because every earlier result from this
row was produced by an index that answered confidently while holding almost
nothing. It now reports integrity consistent with live and claimed counts equal,
all three generations succeeded, the watcher running, and a named-file count that
tracks the real tree. Two unrelated probes returned disjoint results, and a probe
for a module created hours earlier found it, which a stale snapshot cannot fake.

Three of the original probes had recorded concrete MISSES, and all three now
resolve to their canonical owner. The one-shot digest probe previously returned a
release-readiness module; it now returns the canonical core hashing helper plus
the recurrence gate whose own docstring states every audited production body
delegates to it, with the only competing hit being a streamed file digest in dev
tooling, a different concern. The namespace-registry probe previously returned an
auth operator test; the canonical typed registry is now the top hit by a wide
margin. The duplication probe previously returned an unrelated CLI command; it now
returns the single duplication runner, and the health report that consumes it
states it delegates the whole measurement to that one runner, so the second
command-builder this probe exists to catch has not returned.

The removal check needs care in how it is read. The expectation recorded against
it was that it must return nothing, but semantic search always returns nearest
neighbours, so an empty result was never achievable and its absence is not a
finding. What matters is whether the retired concept itself reappeared. It has
not: the hits are the evidence-bundle subsystem, which legitimately exists, and an
exact search confirms the only replay implementation in the tree is the unrelated
agent-evaluation harness.

## Notes

The honest conclusion is about the instrument, not the codebase. Three findings
that read as duplication risks were the signature of an index holding almost no
content, which is why they resolved without a single line of production code
changing. A finding produced by a tool that reports success while degraded is not
evidence, and this row is the demonstration.

Partial by design: four probes were run, chosen because each had a recorded prior
result to compare against, which is what makes a rerun meaningful. The remaining
eight had no recorded miss and no removal expectation, so rerunning them would
produce a first observation rather than a delta and would not close anything.
