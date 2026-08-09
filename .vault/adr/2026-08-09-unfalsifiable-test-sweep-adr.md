---
tags:
  - '#adr'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:1c9c98c2719044c084b3f94df476205e26c0de4ef7c2a2b3c78b3cc0515c6b45'
related:
  - "[[2026-08-09-unfalsifiable-test-sweep-reference]]"
---
# `unfalsifiable-test-sweep` adr: `A corpus scan carries its own floor` | (**status:** `accepted`)

## Problem Statement

A test that scans a corpus and asserts it found no violations reports exactly
what a clean tree reports when the walk returns nothing. The measurement in
`2026-08-09-unfalsifiable-test-sweep-reference` found one such scan
unfalsifiable today and a second protected only by accident.

A decision is needed because the accidental protection is the interesting case.
It looks like a working guard, and it disappears as a direct consequence of the
project succeeding at the cleanup the guard exists to drive.

## Considerations

- The repository already floors its two shared corpora in a dedicated module,
  so the pattern exists and is proven; what is missing is its application to
  module-local corpora.
- The vacuity screen deliberately over-reports and states it cannot judge
  whether a flagged scan is genuinely unprotected.
- A ratchet's entry count is not a stable quantity. It is designed to fall.

## Considered options

- **Rely on the inert-ratchet check.** Rejected: it protects only while the
  ratchet is non-empty, and the dev ratchet reaching zero has already
  demonstrated the failure.
- **Floor every corpus centrally in the shared floor module.** Rejected: that
  module floors shared fixtures, and these accessors are module-local. Reaching
  into them from outside would invert the ownership.
- **Assert an exact expected file count.** Rejected: it fails on ordinary
  deletions, so it trains the reader to edit the constant, and this project's
  own rules forbid gating on a tally rather than a property.
- **Give each module-local corpus its own collapse floor.** Chosen.

## Constraints

- The floor must sit far enough below the live count that routine churn cannot
  trip it, or it becomes a constant people update reflexively.
- It must not depend on any ratchet, allowlist or backlog whose size is
  expected to change.

## Implementation

Each test module that walks a corpus through a module-local accessor and
asserts an absence carries a companion test asserting the walk returned more
than a collapse floor. The floor is set roughly an order of magnitude below the
live count, and its message tells the reader to fix the walk rather than lower
the floor.

## Rationale

The knockout criterion is independence: a scan's protection must not be a side
effect of state that is expected to reach zero. A floor keyed on the corpus
itself holds regardless of how much backlog remains, which is exactly the
property the accidental protection lacked.

Setting the floor low rather than tight is deliberate. The question being asked
is "did this walk collapse", not "is the tree the size I remember", and a floor
that answers the second question loudly and often stops being read.

## Consequences

Both scans can now fail when their corpus collapses, and the production
backlog can drain to zero without silently disabling its own gate.

The honest limit: a floor catches a collapse, not a narrowing. A walk that
still returns most of the tree while quietly missing one directory passes this
and remains undetected. Closing that needs a per-scan measurement against a
known target and a near-miss, which is per-gate work a floor cannot do.
