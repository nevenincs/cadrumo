---
tags:
  - '#adr'
  - '#modelo-editor-workbench'
date: '2026-10-02'
modified: '2026-10-01'
body_schema: 'body-v2'
body_hash: 'sha256:9712d5a13c0de996453c5e36b79253656b8ce7f1c94f3c68efb122e96e66280f'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-audit]]"
---

# `modelo-editor-workbench` adr: `Atomically replace generated export and form-layout companions` | (**status:** `rejected`)

## Problem Statement

S62 annotates exact official numeric rate literals. Export fields feed generated form layouts, so the generated source families must converge before authority publication. The proposal sought a whole-revision source transaction to replace both families together.

## Considerations

The first experiment added target companion checks to the existing export-only source journal. Those new checks refused a changed layout before export installation. The existing accepted generator-authority ADR owns export replacement; the accepted workbench ADR owns form-layout generation and published-authority reads. The project registry-authority rule distinguishes editable source from validated candidates and active published generations.

## Considered options

- One receipt-bound selected revision directory cutover, restricted to generated export and form_layouts: proposed initially, then rejected as unnecessary for this step. It would add a costly source transaction boundary and grouped recovery contract.
- Separate existing export and form-layout source owners, followed by complete validation and atomic authority descriptor publication: retained within the accepted decisions. Interrupted source authoring remains stale and fail-closed, while consumers retain the complete prior published generation.
- Ignoring stale layout validation or publishing a partial generation: rejected; neither is permitted.

## Constraints

This rejected proposal adds no binding constraint and changes no accepted decision. Complete candidate validation, exact literal-byte preservation, source-pinned presentation scales, generated-layout source-digest validation, authored-family preservation, the existing opaque export rollback journal and separate atomic authority publication remain required by their current owners.

## Implementation

Do not implement the proposed whole-revision journal or extend its write ownership. Retain isolated candidate companion regeneration and full candidate validation. Remove only the new uncommitted target companion checks, install exports through the existing canonical republish owner with consumers quiet, regenerate layouts through the existing form-layout owner, and run their checks and full authority validation before descriptor publication. A source interruption is repaired by rerunning these owners; it cannot promote an incomplete runtime generation.

## Rationale

The original rejection of separate source generation conflated installed editable source with active published authority. Read-only investigation of dev/registry/form_layout/cli.py, dev/registry/pipeline/_tree_publication.py, 2026-09-30-modelo-editor-workbench-adr and aeat-registry-authority-flow establishes that the source authoring interval is already covered. The grouped source rollback guarantee would be stronger, but S62 does not require it.

## Consequences

The whole-revision proposal is withdrawn before authorization or implementation. The user was informed that its pending approval question is unnecessary. No accepted ADR was amended, no new journal rolled out and no source or descriptor published by this proposal. S62 continues through the approved plan and existing generator/publication boundaries.
