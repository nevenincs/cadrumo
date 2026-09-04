---
tags:
  - '#adr'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6e631874def50fbf2a532fb6ddbd3e95a6aadcc0e2b73854e422196d9e4ab49d'
related:
  - "[[2026-09-04-reachability-burndown-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace reachability-burndown with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
  reference: test support, harness code, superseded capability, deliberately staged
  capability, orphaned capability, capability that should be live, or deferred by
  ownership.
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

## Consequences

- The gate will cover symbols and orphaned test modules, which it does not today.
- Some findings resolve to `[[intentional]]` with a recorded rationale; the count closes
  on classified resolution rather than on an integer reaching zero.
- Relocation moves code out of the shipped wheel, which changes the distributed artifact
  and must be verified against the packaging gates.
- The TUI population stays open until its owning campaign lands, so this campaign cannot
  close the module count alone.
- Each deletion of product capability is recorded with the decision authorising it.
