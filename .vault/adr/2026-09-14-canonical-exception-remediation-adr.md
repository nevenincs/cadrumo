---
tags:
  - '#adr'
  - '#canonical-exception-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:03841d59cdbb5756a1e348b3c0a0ba26734ddd143bc729db996fe4a1f9bc140c'
related:
  - "[[2026-09-14-canonical-exception-remediation-migration-taxonomy-research]]"
  - "[[2026-09-14-canonical-exception-remediation-production-inventory-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace canonical-exception-remediation with a kebab-case feature tag, e.g. #foo-bar.
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

# `canonical-exception-remediation` adr: `Canonical registered exception ownership` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Cadrumo-owned failures rooted directly in built-in exception classes bypass the
canonical registry and cannot promise stable downstream envelopes. The campaign needs
one rule for ownership, ancestry, binding, and external translation.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- Exact source and descendant closure are grounded by
  `2026-09-14-canonical-exception-remediation-production-inventory-reference`.
- Registry, envelope, retryability, and external-boundary tradeoffs are grounded by
  `2026-09-14-canonical-exception-remediation-migration-taxonomy-research`.
- Canonical defining modules must preserve dependency direction and avoid facades.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- Keep rationale-backed built-in roots: rejected because acknowledgements do not create
  registry identities or envelopes.
- Centralize all exception definitions: rejected because it displaces ownership and
  creates cross-layer import coupling.
- Register package-owned exceptions and translate only at proven external protocols:
  accepted because it preserves ownership and supplies one machine-readable contract.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

`CadrumoError` import-time binding requires a registry row before a migrated class is
imported. Every descendant must bind exactly once. Third-party callbacks may receive a
built-in translation only at their narrow protocol boundary. The existing registry and
envelope system is stable and already enforced by focused gates.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

Keep concrete definitions in their owning modules. Replace direct built-in ancestry
with `CadrumoError`, `CoreError`, `CoreValidationError`, or an existing specific
registered root. Enroll exact fully qualified identities in layer registry shards,
provide localized message keys, update concrete catches, and remove rationale metadata.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

This is the only option that simultaneously satisfies canonical ownership, stable
envelopes, non-facade imports, and narrow interoperability, as established by the two
related grounding records.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Downstream consumers receive stable codes and redaction-safe envelopes for all owned
failures. The migration is broad: registry enrollment and ancestry changes must land in
coherent batches, and catches that formerly depended on built-in polymorphism require
focused review. Future bare roots become gate failures rather than rationale entries.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
