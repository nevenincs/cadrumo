---
tags:
  - '#adr'
  - '#recovery-mnemonic-presentation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1c2ad95d2ef18983809ce975087ad5ae23c668d8fa759d9827fc431a64a0471d'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace recovery-mnemonic-presentation with a kebab-case feature tag, e.g. #foo-bar.
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

# `recovery-mnemonic-presentation` adr: `recovery mnemonic presentation and handling` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Mnemonic encoding and one-time presentation remain useful operator-surface decisions after recovery custody becomes optional and independent.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- Recovery authority, artifact import/export, and password-reset semantics belong to `2026-08-13-profile-password-custody-adr`.
- Mnemonic plaintext is a secret and must not enter durable results or logs.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- Store or repeatedly display the mnemonic: rejected because it multiplies secret exposure.
- One-time explicit handoff with verification: accepted.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

The wordlist and encoding version are canonical and locale-independent. Presentation must preserve exact word order and spacing.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

Recovery enrollment presents mnemonic words once through a secret-capable interactive surface or bounded secret descriptor. The operator confirms possession through an explicit verification step before the recovery record becomes enrolled. Durable application results carry only version, enrollment state, and a non-secret fingerprint. Logs, telemetry, action envelopes, clipboard automation, shell history, and normal JSON output never contain words. Import accepts mnemonic only through the secret channel and zeroizes transient buffers.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

This keeps human handling stable without making presentation state part of login or custody authority.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Lost mnemonic words cannot be redisplayed. Password login remains unaffected, and a new recovery enrollment requires current-password authentication.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
