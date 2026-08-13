---
tags:
  - '#adr'
  - '#profile-session-lifecycle'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1473d43cec98c0a68ad4a8bf169027306507b6a7b47f7e0ee3402a726ee008f5'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace profile-session-lifecycle with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-session-lifecycle` adr: `authenticated profile session lifecycle` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

The application still needs one explicit active-profile session lifecycle after session-key custody moves to the roll-up.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- Cryptographic session creation, deadlines, handover ordering, and keyring acceleration belong to `2026-08-13-profile-password-custody-adr`.
- UI and command surfaces must project application session truth.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- Let each entrypoint own session state: rejected because state and cleanup diverge.
- Keep one application lifecycle owner: accepted.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

Presentation cannot synthesize authentication, revive a retired session, or convert a keyring failure into profile failure.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

One application service owns active-session observation, explicit close, inactivity events, process shutdown cleanup, and operator-safe status projection. Entrypoints request transitions and render typed outcomes. They do not manipulate keys or session files. Failed candidate authentication leaves the current application session unchanged; the custody roll-up defines the underlying atomic handover.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

One lifecycle owner gives every CLI and TUI surface the same active-profile truth without duplicating custody.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Operator surfaces remain consistent. The service depends on, but does not restate, the custody session contract.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
