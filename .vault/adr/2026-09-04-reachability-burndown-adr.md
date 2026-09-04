---
tags:
  - '#adr'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:3e54b42e0146238a84d7659326ddd9febb0c0dee124e86e9a2a61c85cf3b4918'
related:
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` adr: `Reachability closure through classified resolution` | (**status:** `proposed`)

## Problem Statement

The shipped package carries 43 modules and 1408 symbols that no declared console script
reaches, plus 21 orphaned test modules. The standing ratchet exits 0 against this tree
because it adjudicates modules only, defers a frozen prefix, and carries fourteen
allowed entries; symbols and orphaned tests are ungated entirely. The product therefore
ships code that cannot be reached while its gate reports green. This record decides what
closure means for that backlog and how each finding is resolved without weakening the
instrument that found it.

## Considerations

- A green ratchet is not evidence of a zero backlog; 1408 symbol findings sit outside
  every gate; `2026-09-04-reachability-burndown-reference`.
- Reachability establishes that code is not reached, never why. Duplicated, superseded,
  deliberately staged, and genuinely orphaned code all present identically to the audit.
- Outside-use labels already separate the population: 27 modules are reached only by
  tests, 11 by dev and tests, 2 by dev alone, 3 by nothing.
- 26 of the 49 module findings are inside `cadrumo.entrypoints.tui`, an in-flight surface
  owned by another campaign.
- Deleting or relocating shipped capability changes the product surface and is not a
  reversible tidy-up.
- The duplication campaign proved that a bar reachable only through a forbidden act
  invites quiet relabelling rather than resolution; `2026-09-03-duplication-burndown-adr`.
- Baselines, ratchet widening, and allowlist growth are forbidden;
  `2026-07-14-honest-all-green-adr`.

## Considered options

- **O1 — Delete everything unreachable.** Rejected: it discards deliberately staged
  capability and test support that has a correct home, and it cannot distinguish an
  orphan from a module awaiting its wiring.
- **O2 — Widen the ratchet to cover symbols and orphaned tests, then baseline the
  current count.** Rejected: a baseline is the exact instrument-weakening the honesty
  decision forbids, and it would freeze 1408 findings as permanently acceptable.
- **O3 — Classify every finding into one of a closed taxonomy, resolve each by the remedy
  its class dictates, and extend the gate to symbols and orphaned tests as the backlog
  clears.** Chosen.
- **O4 — Leave symbols ungated and track only modules.** Rejected: it preserves the false
  green this record exists to close.

## Constraints

- Every finding resolves into exactly one class of the closed taxonomy recorded in the
  reference: test support, harness code, design-time authority, superseded capability,
  deliberately staged capability, orphaned capability, capability that should be live, or
  deferred by ownership.
- Harness code and design-time authority are separated by what the code IS, not by who
  reads it. Harness code is written to serve the harness and relocates beside its dev
  consumer. A design-time authority is a product declaration that constrains other
  declarations; its only reader being a conformance gate is how a locked design is
  enforced, and relocating one into `dev/` would move the product's own design out of the
  product.
- Classification is evidenced, not asserted. Supersession requires a named live module
  that discharges the responsibility, found by semantic search rather than by name
  similarity. Deliberate staging requires an accepted decision that records the
  dependency being waited on.
- Resolution is by relocation, deletion with tests, wiring, or an `[[intentional]]`
  classification carrying its rationale. No threshold, exclusion, baseline, skip, or
  allowlist widening, and the `allowed` list stays shrink-only.
- Deletion or relocation of shipped capability requires its owner's recorded decision
  before execution.
- The `cadrumo.entrypoints.tui` prefix stays deferred while its owning campaign is in
  flight. Deferral is scope, never permission.
- Test-only and dev-only use never counts as use. Moving code to its correct home is the
  remedy, not reclassifying the caller.
- The gate extends to unused symbols and orphaned test modules once their populations are
  classified. Extension is shrink-only from the day it lands.

## Implementation

Survey first, resolve second. Classify the population by outside-use label and area, then
work one area at a time, smallest blast radius first: dev-only harness code, then
test-only support, then the symbol backlog by owning package, then the modules requiring
an owner decision.

Ground every classification with semantic search before acting. Query the behaviour and
its domain nouns restricted to production to find a live equivalent, query the type's
responsibility for class-level supersession, and query the decision corpus to recover
whether a capability was staged deliberately. Confirm exact symbols with grep before
editing.

After each area, re-measure the audit, run the owning tests, and shrink the ratchet by
the entries the work resolved. Extend the gate to symbols and orphaned tests once those
populations carry classifications.

## Rationale

O3 is the only option that removes the false green without either discarding decisions or
freezing the debt. The taxonomy is what makes the backlog tractable: the audit reports one
undifferentiated population, while the remedies differ completely, and applying the wrong
remedy is how capability gets deleted or how dead code gets wired to nothing.

Requiring evidence for the two dangerous classes — supersession and deliberate staging —
is what keeps classification from becoming relabelling. Both are claims about intent that
a name cannot establish, which is why semantic search over code and over the decision
corpus is a constraint here rather than a convenience.

### Amendment - design-time authority separated from harness code

The original taxonomy had one class for "reached only by `dev/`", and execution proved it
conflates two different things. Attempting the relocation remedy on the four modules first
classified as harness code showed every one to be a product declaration: the locked CRUD
design for the operator CLI, the contract types it instantiates, the supported calculation
workflows, and the single authoritative home for registry record-specification constants.
Relocating any of them would have moved the product's own design into `dev/`, and in the
registry case would have moved filing-grade constants out of the registry authority.

The class already existed in the tree without a name: `cadrumo.core.address_components`
carries `design_time_authority` in the module ratchet for exactly this shape. The taxonomy
now names it, and the remedy for the class is an `[[intentional]]` classification rather
than a relocation.

## Consequences

- The gate will cover symbols and orphaned test modules, which it does not today.
- Some findings resolve to `[[intentional]]` with a recorded rationale; the count closes
  on classified resolution rather than on an integer reaching zero.
- Relocation moves code out of the shipped wheel, which changes the distributed artifact
  and must be verified against the packaging gates.
- The TUI population stays open until its owning campaign lands, so this campaign cannot
  close the module count alone.
- Each deletion of product capability is recorded with the decision authorising it.
