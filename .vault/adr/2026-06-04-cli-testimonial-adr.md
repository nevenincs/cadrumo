---
tags:
  - '#adr'
  - '#cli-testimonial'
date: '2026-06-04'
modified: '2026-08-25'
body_hash: 'sha256:a2dd1e4ece5c666c0555f4f9ef4f9a3101acc52d735285623750b16fa52b4572'
related:
  - '[[2026-06-30-cli-persona-testimonials-w05-closure-audit]]'
---

# `cli-testimonial` adr: `retrospective authority alignment` | (**status:** `accepted`)

## Problem Statement

The linked plan records had implementation or audit history but no explicit ADR authority edge. That made schema validation fail and left semantic search without a clear decision source for developer briefings.

## Considerations

This ADR is a vault-curation alignment record. It does not reopen the implementation, change runtime behavior, or supersede the original plan evidence. Its purpose is to make the existing authority chain explicit and navigable.

## Constraints

The cleanup is restricted to the vault. Body wiki-links are avoided; frontmatter related fields carry the navigation edges required by the vault checks and by semantic discovery.

## Implementation

Treat the linked plan records as historical execution sources and the linked research records as the evidence bridge for this retrospective authority alignment. Future work should brief from the current linked ADR and research pair before acting on older plan details.

## Rationale

Adding an explicit ADR edge prevents plans from briefing developers without a decision source. Keeping the record retrospective prevents the cleanup itself from inventing a new architectural mandate.

## Consequences

Schema validation can resolve plan-to-ADR authority, and semantic search can find the current decision edge. If a later ADR supersedes this alignment record, it must update frontmatter links on the associated plans and research notes.

## Codification candidates

No project rule is promoted from this retrospective alignment alone.
