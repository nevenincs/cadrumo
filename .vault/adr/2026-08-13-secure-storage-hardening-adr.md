---
tags:
  - '#adr'
  - '#secure-storage-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:48cb5a282400196459041d666a77e170ee7c527faa0dee9471d850649e4f484d'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace secure-storage-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# `secure-storage-hardening` adr: `non-custody secure storage hardening` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Secure storage still needs canonical data taxonomy, permission, validation, and diagnostic boundaries after shared-master custody is removed.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- Password and DEK authority belongs only to `2026-08-13-profile-password-custody-adr`.
- Financial payloads remain secure-storage-only.
- Diagnostics must not disclose profile secrets or financial content.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- Preserve provider-oriented hardening: rejected because provider fallback is superseded.
- Retain storage controls independent of custody: accepted.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

Every durable artifact must have one taxonomy owner, bounded parser, no-follow path resolution, restrictive permissions, and explicit integrity handling.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

The storage taxonomy remains the canonical inventory for profile data, transactions, caches, exports, and local deletion. Writers stage, fsync, atomically replace, and fsync parents where the owning protocol requires durability. Readers reject duplicate members, unknown schema, traversal, links, reparse points, and oversized input before allocation. Logs and typed errors expose operation, UUID-safe correlation, and error class, never passwords, keys, mnemonics, tax identifiers, or payload content. Custody files and their transactions follow the roll-up instead of a generic provider abstraction.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

These controls remain valid for every encrypted storage format and do not depend on how its DEK is wrapped.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Hardening remains centralized while shared-master, AUTO, fallback, and legacy-read rules disappear.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
