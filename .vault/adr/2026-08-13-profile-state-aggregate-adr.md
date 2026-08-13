---
tags:
  - '#adr'
  - '#profile-state-aggregate'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ce2dde2143a003d00b5a4fd7c5ea6a498dd17007657c57c5e878e2e95349f0f8'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace profile-state-aggregate with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-state-aggregate` adr: `non-authoritative profile state projection` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Profile views need a coherent aggregate without turning copied custody fields into authority.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- The password envelope and independent recovery record are authoritative only in their owners.
- Projection drift must not block valid password login.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- Mirror custody facts into the aggregate as gates: rejected.
- Project non-secret status with provenance: accepted.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

The aggregate contains no password KDF, wrapped DEK, recovery wrap, session key, or backend selector.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

The profile aggregate projects immutable UUID, label, current-format presence, local data summary, and typed non-secret lifecycle status from canonical owners. Every projected value carries provenance or a typed unavailable state. Custody generation or recovery enrollment may be displayed only when explicitly obtained from the relevant owner; copied manifest values never select keys or authorize actions. Projection repair follows committed authority and remains idempotent.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

A read model serves UI and CLI needs without becoming a second semantic home.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Some views may report unavailable status instead of guessing. Valid password custody remains independent of stale projections.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
