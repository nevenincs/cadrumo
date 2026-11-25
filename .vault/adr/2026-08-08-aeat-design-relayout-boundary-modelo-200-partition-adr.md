---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-11-04'
body_schema: 'body-v1'
body_hash: 'sha256:caa70d92962ee2db87f7ed8ec11439f9ce179d4eaf1b4c75df5a10890345f14c'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
  - '[[2026-09-02-aeat-design-relayout-boundary-research]]'
---
# `aeat-design-relayout-boundary` adr: `Modelo 200 partitions by 2024 design authority and reviewed semantic crosswalk` | (**status:** `accepted`)

## Problem Statement

The accepted revision split remains necessary: the pre-existing range covered a material AEAT design re-layout, so the earlier design's filing years must select a revision specific to that design and later years must select their own applicable revision.

This amendment corrects the earlier premise that a physical sibling relationship authorizes wholesale semantic inheritance. `2026-09-02-modelo-200-semantic-crosswalk-research` establishes that the later revision is not semantic authority for the target year. The target revision, the one for the earlier design, must be generated from its own exact official design, with every semantic association and legal reference independently admissible for its filing years.

A decision is needed because the form's scale makes hand-authoring generated coordinates and fragments untenable, while automatic sibling copying or description matching would convert diagnostic evidence into filing authority.

## Considerations

- The accepted parent relayout boundary and existing period-selector partition remain stable.
- `2026-09-02-modelo-200-semantic-crosswalk-research` falsifies the prior wholesale-inheritance premise and defines the evidence boundary for target-first repair.
- `2026-08-10-aeat-export-fragment-generator-authority-adr` remains governing: the exact official design owns physical facts, a reviewed semantic map owns meaning, and the generator publishes only a complete validated target.
- Registry authority is fail-closed: a candidate, partial map, ungrounded legal reference, or source mismatch cannot establish filing capability.
- The workflow must remain practical at Modelo 200 scale without making automation an unreviewed semantic author.

## Considered options

**Continue wholesale sibling inheritance. Rejected.** Presence, position, or apparent similarity in a later revision does not prove target-design meaning, section, semantic role, or legal grounding.

**Hand-author the target export tree and coordinates. Rejected.** It creates an unreviewable volume of duplicate physical-layout work and bypasses generated authority.

**Automatically write normalized-description cross-revision matches. Rejected.** Description normalization, compatible type and length, and legal-window screening are diagnostics, not independent semantic proof.

**Generate from the target design after a complete reviewed target-first semantic map. Chosen.** The exact design supplies physical facts; narrowly proven same-year templates may repair target semantics; cross-revision analysis creates review proposals only; and publication remains unavailable until every target anchor has reviewed semantic and legal authority.

## Constraints

The revision named `2024` serves only the filing years of its own design; the later revision serves its own law-selected period. This amendment does not reopen naming, epoch selection, or the parent relayout decision.

The exact pinned target design owns record membership, ordering, offsets, lengths, field types, literals, validation metadata, and all other wire facts present in that source. Neither a later design nor an existing fragment tree may override them.

Every target semantic-map entry remains bound to the exact target source reference and SHA-256 and must classify one exact source anchor to an admissible canonical owner, typed producer, literal, reserve, draft field, or revision-admitted typed projection. The map remains complete and bijective under `2026-08-10-aeat-export-fragment-generator-authority-adr`.

A same-design template may support a narrow repair only where exact target-year evidence proves normalized meaning and compatible wire type. It cannot populate a class of anchors, infer a novel owner, reuse an incompatible legal reference, or weaken source proof.

A cross-revision normalized-description match may be emitted solely as a review proposal. It cannot write target authority, select a role or section, establish continuity, or carry legal references into the target revision until a reviewed adjudication records target-year meaning and authority.

A novel, conflicting, ambiguous, absent, duplicate, source-drifted, or otherwise unadjudicated target anchor remains refused. No sibling fallback, nearest-text ranking, implicit default, untyped value bag, or partial publication is permitted.

Every legal reference used by a target-revision declaration or map entry must independently cover the target filing years and legal window. A later-year citation, proximity match, or proposal is not target legal authority.

## Implementation

Retain the revision partition and replace inheritance with a target-first workflow.

The tooling parses the exact pinned target design and constructs a semantic worklist keyed by exact target anchors. It distinguishes:

- exact target-year template repairs satisfying the narrow proof;
- cross-revision candidates retained as non-authoritative review proposals;
- new target declarations requiring direct target adjudication; and
- conflicting, ambiguous, or unsupported anchors retained as refusals.

Reviewed adjudications are recorded in source-hash-bound target semantic-map authority with target-year legal grounding and reviewer provenance. Candidate tooling may produce deterministic review material and proposal diffs, but never writes authority merely because a candidate is unique or similar.

The generator receives only the exact target design, complete reviewed target semantic map, applicable reviewed render profile, and selected target revision. It derives coordinates, export fragments, and static provenance programmatically. It does not accept a sibling tree, proposal, or unreviewed worklist row as authority.

Generation occurs in a fresh temporary target. Before publication, tooling validates source/SHA identity, parser-map bijection, revision source membership, complete semantic coverage, legal applicability, render-profile coverage, generated provenance, loader semantics, and export-tree consistency. Any unresolved anchor or validation failure refuses the whole target.

Only a fully validated temporary target may be atomically published. Publication verifies staged and destination identity under the established locking and receipt discipline.

## Rationale

This is the narrowest correction preserving safety and scale. The split remains correct, and generation remains the credible way to create the physical export surface. What changes is semantic proof: the grounding research shows sibling reuse and text similarity cannot bear it.

The official target design determines where and how a field exists; the reviewed map determines what it means; legal grounding independently determines whether that meaning applies. Same-year templates retain limited value, cross-revision analysis remains a review aid, and explicit refusal protects every unadjudicated target.

## Consequences

Modelo 200 can reach a complete generated target export surface without hand-authoring thousands of coordinate fragments. Output is reproducible from source-hash-bound target authority and validated before publication.

The partition remains intact, but target semantics must be established against the target source. Existing declarations or references relying on later-year authority require reconciliation through the target-first workflow.

Review effort concentrates on semantic adjudication rather than geometry. Entries that cannot be mechanically resolved remain unavailable rather than becoming filing-capable by similarity or fallback.

This amendment removes the general rule that adjacent revisions may inherit whole casillas merely because they appear in both designs. Future reuse requires exact source-anchor and reviewed-adjudication proof.
