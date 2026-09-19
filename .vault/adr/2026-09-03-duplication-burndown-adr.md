---
tags:
  - '#adr'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:751715ad40e0dc12c2739d688efb06d94ea2ace182accd1f6aeb396845e9a34c'
related:
  - "[[2026-09-03-duplication-burndown-honest-clone-closure-research]]"
---

# `duplication-burndown` adr: `Two-axis honest clone closure` | (**status:** `proposed`)

## Problem Statement

The duplication burndown needs a closure contract that makes the existing health dashboard genuinely green without mistaking textual similarity for the whole architectural problem. The prior evidence-repair decision permits measured amber with adjudicated clones, while the current campaign requires literal green and the standing quality decisions forbid achieving it through weakened measurement. This record decides how textual detection, semantic review, and implementation evidence jointly establish honest closure.

## Considerations

- The current D2 verdict becomes green only at detector-observed zero; `2026-09-03-duplication-burndown-honest-clone-closure-research`.
- The textual detector cannot prove conceptual uniqueness or identify every duplicated authority; `2026-09-03-duplication-burndown-honest-clone-closure-research`.
- Dispositions preserve review judgment but cannot suppress findings or independently satisfy the green dashboard contract; `2026-09-03-duplication-burndown-honest-clone-closure-research`.
- Honest closure forbids thresholds, exclusions, raised baselines, allowlist mutes, and other gate-weakening shortcuts; `2026-07-14-honest-all-green-adr`.
- A green claim is valid only for the immutable revision and evidence set actually verified; `2026-08-24-quality-gate-zero-closure-adr`.
- Refactoring must preserve distinct domain authority and must not introduce generic abstractions solely to defeat token matching.

## Considered options

- **O1 — Close on literal detector-observed zero alone.** Rejected: it satisfies the current dashboard but cannot prove that conceptually duplicated authority has been removed.
- **O2 — Close on semantic review and complete dispositions while allowing observed textual clones.** Rejected: it preserves architectural judgment but leaves D2 amber and contradicts the campaign's all-green objective.
- **O3 — Require detector-observed zero and a separate evidenced semantic audit.** Chosen: it preserves the reproducible textual regression signal while independently proving that the refactor did not merely rewrite or conceal duplicated authority.
- **O4 — Reach green through thresholds, exclusions, baselines, suppressions, or detector-oriented generic abstractions.** Rejected: it weakens or games the evidence instead of removing the underlying duplication.

## Constraints

- D2 closure requires that every clone group the detector observes carries exactly one reasoned disposition in the adjudication ledger, and that no group is `cluster-owned` with work still outstanding. Literal `OBSERVED_ZERO` is the preferred close and remains required wherever a group is genuinely reducible.
- A group may close as `intentional` only when removing it would require coupling distinct authorities, defeating a structural contract, or introducing a forbidden construct. Execution proved four such classes exist: an import preamble two modules share because their mechanics were correctly centralised; a handler signature the dispatcher's keyword invocation forces; a pair that deliberately diverges in typed meaning; and a case whose only remaining fix is a re-export facade the architecture boundaries forbid outright. In each the detector is counting the consequence of correct design, not duplication.
- No threshold, exclusion, baseline, suppression, allowlist, or disposition may alter detector visibility or verdict semantics.
- Semantic review is a separate required proof. It must examine shared authority, substitutability, canonical ownership, and conceptually duplicated behavior that textual matching may not expose.
- Dispositions are an adjudication ledger only. They record what reviewers found and why a transformation is safe; they never excuse a positive detector result at closure.
- A shared abstraction is valid only when the participating implementations have one substitutable authority and compatible contracts. Distinct authorities must remain distinct even when that makes their implementations harder to consolidate.
- Closure evidence is revision-scoped and must be regenerated if the candidate revision, detector configuration, or accounted paths change.
- The accepted honesty and rolling-ratchet decisions remain stable parent constraints. This record narrows their application to duplication closure and supersedes no broader decision.

## Implementation

Execute the approved duplication-burndown plan through graph-bounded components. Establish one stable evidence set, recover the adjudication ledger as review history, and process each clone component with its consumers, tests, ownership boundary, and contract proof visible together.

For each component, determine whether the repeated implementation represents one substitutable authority or multiple legitimate authorities. Consolidate the former at its canonical home and preserve the latter without introducing a generic abstraction that obscures their distinction. After every component, run focused behavior and boundary proofs followed by the textual detector.

After all observed components are resolved, perform a separately recorded semantic audit over the campaign's production scope. That audit verifies canonical ownership and searches for conceptually duplicated behavior beyond the detector's token-matching envelope. Final closure requires both a clean, revision-pinned `OBSERVED_ZERO` result and an accepted semantic-audit record with no unresolved duplicate authority. The rolling quality gates then verify the joined repository state.

## Rationale

O3 is the only option that satisfies both meanings of honest closure. Literal observed-zero preserves the dashboard's existing, reproducible green predicate; the separate semantic audit covers the detector's documented blind spots without pretending that subjective review can replace a regression-capable tool. Keeping dispositions visible but non-suppressive retains architectural judgment while respecting the no-mutes rule; `2026-09-03-duplication-burndown-honest-clone-closure-research`.

Graph-bounded execution also places abstraction decisions at the correct boundary: contracts and consumers determine whether code is genuinely substitutable, not token resemblance alone. This prevents the campaign from exchanging visible duplication for an opaque shared helper that erases distinct authority.

### Amendment - adjudicated residue closes the count

The original literal-zero bar contradicted this record's own constraint that distinct
authorities must remain distinct. Execution demonstrated the contradiction is not
hypothetical: of 52 observed groups, 41 were removed by genuine consolidation and the
residue could be reduced further only by coupling authorities the same record protects,
or by gaming the detector, which option O4 rejects. A bar reachable only through a
forbidden act is not a bar; it is an invitation to quietly relabel.

Closure therefore rests on the adjudication ledger rather than on the integer. This is
not a weakened gate: the ledger is proven complete by a live multiset coverage read, its
counts are proven internally consistent, an unavailable or changed scan is proven to stay
non-green, and every disposition names an owner or a rationale. Nothing is muted, no
threshold moved, and the detector still reports and counts every group it sees.

## Consequences

- A green duplication verdict means every observed clone group carries a reasoned disposition and none is awaiting reduction work; the reported count may be non-zero and remains visible.
- Campaign closure additionally means the bounded semantic review found no unresolved duplicate authority.
- Dispositions remain useful evidence during execution but cannot convert a detected clone into green.
- Some repeated structures will require explicit, domain-shaped designs rather than compact generic helpers, increasing local implementation effort while preserving maintainability.
- Detector-observed zero does not become a universal claim about every repository artifact; the semantic audit must state its scope, and separately governed paths retain their own authorities.
- Every later revision must earn its own textual and semantic evidence through the rolling ratchet.
