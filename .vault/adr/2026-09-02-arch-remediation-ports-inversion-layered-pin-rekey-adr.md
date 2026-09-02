---
tags:
  - '#adr'
  - '#arch-remediation-ports-inversion'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8559412b80294fce681b2c065aac11ef03663873ac4e85ac83285119124a0271'
related:
  - "[[2026-07-08-importlinter-test-carveout-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - "[[2026-09-02-arch-remediation-ports-inversion-layered-pin-provenance-reference]]"
---

# `arch-remediation-ports-inversion` adr: `Re-key displaced production pins rather than invert` | (**status:** `accepted`)

## Problem Statement

The `AEAT layered architecture` contract was the last broken import contract in
the repository, reporting eighty-two production violations while the other ten
contracts passed. A decision was needed on how to close it, and the two
available answers point in opposite directions: invert each dependency behind a
protocol, or record the residual edge with its rationale. Choosing wrongly is
expensive in both directions. Inverting an edge that a standing decision
permits spends a large refactor to contradict that decision; recording an edge
that is genuinely un-inverted installs a false rationale, which is the failure
mode that blinded this gate in the first place. The decision could not be
deferred, because a contract reporting eighty-two violations protects nothing:
it cannot distinguish a new violation from the accumulated set.

## Considerations

- All eighty-two edges run from `application` to the adapter tier and no other
  direction, per `2026-09-02-arch-remediation-ports-inversion-layered-pin-provenance-reference`.
- The architecture restructure decision at section 538 permits the application
  layer to import adapters for outbound wiring and defers full inversion; the
  contract's own header prose restates that permission as the reason its
  exception ledger pins application source modules individually.
- The edges were not new. Forty-seven pins were deleted rather than re-keyed
  when their source modules were promoted to public names, and a five-way
  module split redistributed an already-reviewed reach across new names while
  the gate could not report.
- The gate had been blind for an extended period for two independent reasons,
  so the eighty-two accumulated silently rather than arriving together.
- The contract sets `unmatched_ignore_imports_alerting = error`, so an
  overshooting pin fails the run. A re-keyed pin set is self-checking against
  the live graph in a way a wildcard is not.
- Four modules that once held pins now reach nothing outward, so at least one
  standing rationale was already false and had to be retired either way.

## Considered options

- **Re-key each displaced pin at its promoted module and exact target
  (chosen).** Restores the reviewed decision the refactor displaced, keeps
  every rationale attached to a pin that exists, and leaves a new production
  edge failing loudly. Cost: the ledger stays long, and the deferral it records
  remains visible rather than resolved.
- **Invert all eighty-two behind protocols in the application layer.** Would
  remove the ledger entries, but contradicts section 538, which permits the
  construction edge; would relocate roughly forty concrete repositories and
  every composition site in one change; and would make the application layer's
  encrypted-store reach the outlier rather than the ambient design it currently
  is across the package.
- **Widen the contract with package-level wildcards over
  `application -> adapters`.** Cheapest, and rejected: it admits an
  inbound-adapter edge without review, which is precisely the class this
  contract exists to surface, and it discards the per-module review the
  narrowing pass had already paid for.
- **Weaken the contract's layer definitions so the edge is not a violation.**
  Rejected outright: it would retire the gate rather than satisfy it, and the
  peer-tier declaration of the inference package is load-bearing for the
  sibling contracts that pass.
- **Leave the contract broken and rely on the other ten.** Rejected: none of
  the others covers the application-to-adapter direction, so the one class most
  likely to erode would be the one class unguarded.

## Constraints

This record decides how to express edges the architecture decision already
permits; it does not widen that permission, and it does not approve any new
application-to-adapter coupling. It depends on section 538 remaining the
accepted position on application-layer outbound wiring: were that decision
reversed, every pin re-keyed here becomes inversion work rather than a recorded
allowance, and this record would be superseded rather than amended. It also
depends on the gate staying able to report - a contract that aborts before
evaluation silently converts every pin into an unverified claim, which is the
condition that produced this problem.

## Implementation

Each displaced pin is re-attached beneath the rationale comment that already
justified it, keyed at the promoted public module name and at the exact target
module the import names rather than at a package wildcard. Where a refactor
turned one reviewed consumer into several, the successor pins sit together
under a short added note stating that the split moved the reach and did not add
it, so the inherited justification is explicit rather than assumed. Where a
concrete was relocated since the last pin pass and no rationale block existed -
the investment-goods register, the edit-receipt store, the SQL integrity report
consumed by the diagnostics model, and the mobile-identity support surface -
each gets its own stated reason naming why the edge exists and why there is no
port to invert behind it. The stale rationale describing two ledger stores that
now reach nothing is removed rather than re-keyed.

No production module changes. That is the substance of the decision, not an
omission: the edges were already reviewed and are already permitted, so the
correct repair is to the record of them.

## Rationale

The knockout criterion is that inversion here would contradict a standing
accepted decision rather than implement one. Section 538 permits the
construction edge and explicitly defers full inversion, and the contract was
built to enforce that shape - individually pinned production edges, loud
failure for new ones. The eighty-two were never a decision to make; they were a
decision already made and then lost to a rename, as the provenance reference
establishes per class and, for the largest cluster, by reading the pre-split
module's own import list.

Recording is only defensible because it is provable per edge, and that is what
separates this from suppression. Each pin names a real import at a real line,
each carries a reason that is true of that import, and the contract's unmatched
alerting fails any pin that overshoots. The alternative that looked cheapest -
wildcards - fails exactly the test that matters, because it would readmit
without review the inbound-adapter class that the last narrowing pass found
sitting unexamined inside broad pins.

## Consequences

The layered contract reports kept, so `check-imports` is green and a new
production edge into the adapter tier now fails on arrival rather than
disappearing into an eighty-strong backlog. The per-module pin set is
self-checking: the next rename breaks the gate loudly instead of quietly
dropping a pin, provided the gate is allowed to run.

The honest cost is that the deferral is now more visible and more entrenched.
The ledger is longer, and it documents a large application-to-adapter surface
that section 538 permits but that a stricter reading of hexagonal direction
would not. Anyone revisiting that permission inherits a precise inventory of
what would have to move, which is the main thing this pass buys beyond a green
gate.

Two hazards remain. A rationale comment can still outlive its pin, as fifteen
of them did here; nothing structural prevents that, only the discipline of
re-keying rather than deleting. And a blind gate remains the worst failure
mode, because it converts every pin in the file from an enforced claim into an
unverified one - the eighty-two are what that looks like after a few months.
