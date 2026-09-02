---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-09-02'
body_schema: 'body-v1'
body_hash: 'sha256:e88c9e760815394334c156d9d85ab2822fccbfc1985d62f85aa7834133cf3ac9'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
  - '[[2026-09-02-modelo-200-semantic-crosswalk-research]]'
---
# `aeat-design-relayout-boundary` adr: `Modelo 200 partitions by 2024 design authority and reviewed semantic crosswalk` | (**status:** `accepted`)

## Problem Statement

The accepted revision split remains necessary: the pre-existing range covered a material 2024/2025 AEAT design re-layout, so 2024 must select a 2024-specific revision and 2025 onward must select its own applicable revision.

This amendment corrects the earlier premise that a physical sibling relationship authorizes wholesale semantic inheritance. `2026-09-02-modelo-200-semantic-crosswalk-research` establishes that the later revision is not semantic authority for the target year. The 2024 revision must be generated from its own exact official design, with every semantic association and legal reference independently admissible for 2024.

A decision is needed because the form's scale makes hand-authoring generated coordinates and fragments untenable, while automatic sibling copying or description matching would convert diagnostic evidence into filing authority.

## Considerations

- The accepted parent relayout boundary and existing period-selector partition remain stable.
- `2026-09-02-modelo-200-semantic-crosswalk-research` falsifies the prior wholesale-inheritance premise and defines the evidence boundary for target-first repair.
- `2026-08-10-aeat-export-fragment-generator-authority-adr` remains governing: the exact official design owns physical facts, a reviewed semantic map owns meaning, and the generator publishes only a complete validated target.
- Registry authority is fail-closed: a candidate, partial map, ungrounded legal reference, or source mismatch cannot establish filing capability.
- The workflow must remain practical at Modelo 200 scale without making automation an unreviewed semantic author.

## Considered options

**Continue wholesale sibling inheritance. Rejected.** Presence, position, or apparent similarity in a later revision does not prove 2024 meaning, section, semantic role, or legal grounding.

**Hand-author the 2024 export tree and coordinates. Rejected.** It creates an unreviewable volume of duplicate physical-layout work and bypasses generated authority.

**Automatically write normalized-description cross-revision matches. Rejected.** Description normalization, compatible type and length, and legal-window screening are diagnostics, not independent semantic proof.

**Generate from the 2024 design after a complete reviewed target-first semantic map. Chosen.** The exact design supplies physical facts; narrowly proven same-year templates may repair target semantics; cross-revision analysis creates review proposals only; and publication remains unavailable until every target anchor has reviewed semantic and legal authority.

## Constraints

The revision named `2024` serves 2024 alone; the later revision serves its own law-selected period. This amendment does not reopen naming, epoch selection, or the parent relayout decision.

The exact pinned 2024 design owns record membership, ordering, offsets, lengths, field types, literals, validation metadata, and all other wire facts present in that source. Neither a later design nor an existing fragment tree may override them.

Every target semantic-map entry remains bound to the exact 2024 source reference and SHA-256 and must classify one exact source anchor to an admissible canonical owner, typed producer, literal, reserve, draft field, or revision-admitted typed projection. The map remains complete and bijective under `2026-08-10-aeat-export-fragment-generator-authority-adr`.

A same-2024 template may support a narrow repair only where exact target-year evidence proves normalized meaning and compatible wire type. It cannot populate a class of anchors, infer a novel owner, reuse an incompatible legal reference, or weaken source proof.

A cross-revision normalized-description match may be emitted solely as a review proposal. It cannot write target authority, select a role or section, establish continuity, or carry legal references into 2024 until a reviewed adjudication records target-year meaning and authority.

A novel, conflicting, ambiguous, absent, duplicate, source-drifted, or otherwise unadjudicated target anchor remains refused. No sibling fallback, nearest-text ranking, implicit default, untyped value bag, or partial publication is permitted.

Every legal reference used by a 2024 declaration or map entry must independently cover the 2024 target and legal window. A later-year citation, proximity match, or proposal is not 2024 legal authority.

## Implementation

Retain the revision partition and replace inheritance with a target-first workflow.

The tooling parses the exact pinned 2024 design and constructs a semantic worklist keyed by exact 2024 anchors. It distinguishes:

- exact target-year template repairs satisfying the narrow proof;
- cross-revision candidates retained as non-authoritative review proposals;
- new target declarations requiring direct 2024 adjudication; and
- conflicting, ambiguous, or unsupported anchors retained as refusals.

Reviewed adjudications are recorded in source-hash-bound 2024 semantic-map authority with target-year legal grounding and reviewer provenance. Candidate tooling may produce deterministic review material and proposal diffs, but never writes authority merely because a candidate is unique or similar.

The generator receives only the exact 2024 design, complete reviewed 2024 semantic map, applicable reviewed render profile, and selected 2024 revision. It derives coordinates, export fragments, and static provenance programmatically. It does not accept a sibling tree, proposal, or unreviewed worklist row as authority.

Generation occurs in a fresh temporary target. Before publication, tooling validates source/SHA identity, parser-map bijection, revision source membership, complete semantic coverage, legal applicability, render-profile coverage, generated provenance, loader semantics, and export-tree consistency. Any unresolved anchor or validation failure refuses the whole target.

Only a fully validated temporary target may be atomically published. Publication verifies staged and destination identity under the established locking and receipt discipline.

## Rationale

This is the narrowest correction preserving safety and scale. The split remains correct, and generation remains the credible way to create the physical export surface. What changes is semantic proof: the grounding research shows sibling reuse and text similarity cannot bear it.

The official 2024 design determines where and how a field exists; the reviewed map determines what it means; legal grounding independently determines whether that meaning applies. Same-year templates retain limited value, cross-revision analysis remains a review aid, and explicit refusal protects every unadjudicated target.

## Consequences

Modelo 200 can reach a complete generated 2024 export surface without hand-authoring thousands of coordinate fragments. Output is reproducible from source-hash-bound target authority and validated before publication.

The partition remains intact, but 2024 semantics must be established against the 2024 source. Existing declarations or references relying on later-year authority require reconciliation through the target-first workflow.

Review effort concentrates on semantic adjudication rather than geometry. Entries that cannot be mechanically resolved remain unavailable rather than becoming filing-capable by similarity or fallback.

This amendment removes the general rule that adjacent revisions may inherit whole casillas merely because they appear in both designs. Future reuse requires exact source-anchor and reviewed-adjudication proof.
