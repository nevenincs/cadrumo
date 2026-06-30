---
generated: true
tags:
  - '#index'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-05-20-cli-persona-testimonials-audit]]'
  - '[[2026-05-20-cli-persona-testimonials-research]]'
  - '[[2026-05-21-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-cli-persona-testimonials-plan]]'
  - '[[2026-05-22-cli-persona-testimonials-P04-S01]]'
  - '[[2026-05-22-cli-persona-testimonials-P04-S02]]'
  - '[[2026-05-22-cli-persona-testimonials-P05-S01]]'
  - '[[2026-05-22-cli-persona-testimonials-P05-S02]]'
  - '[[2026-05-22-cli-persona-testimonials-P06-S04]]'
  - '[[2026-06-04-cli-persona-testimonials-adr]]'
  - '[[2026-06-30-cli-persona-testimonials-W01-P01-S01]]'
  - '[[2026-06-30-cli-persona-testimonials-W01-P01-S02]]'
  - '[[2026-06-30-cli-persona-testimonials-W01-P01-S03]]'
  - '[[2026-06-30-cli-persona-testimonials-W01-P02-S04]]'
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# `cli-persona-testimonials` feature index

Auto-generated index of all documents tagged with `#cli-persona-testimonials`.

## Documents

### adr

- `2026-06-04-cli-persona-testimonials-adr` - `cli-persona-testimonials` adr: `retrospective authority alignment` | (**status:** `accepted`)  ## Problem Statement  The linked plan records had implementation or audit history but no explicit ADR authority edge. That made schema validation fail and left semantic search without a clear decision source for developer briefings.  ## Considerations  This ADR is a vault-curation alignment record. It does not reopen the implementation, change runtime behavior, or supersede the original plan evidence. Its purpose is to make the existing authority chain explicit and navigable.  ## Constraints  The cleanup is restricted to the vault. Body wiki-links are avoided; frontmatter related fields carry the navigation edges required by the vault checks and by semantic discovery.  ## Implementation  Treat the linked plan records as historical execution sources and the linked research records as the evidence bridge for this retrospective authority alignment. Future work should brief from the current linked ADR and research pair before acting on older plan details.  ## Rationale  Adding an explicit ADR edge prevents plans from briefing developers without a decision source. Keeping the record retrospective prevents the cleanup itself from inventing a new architectural mandate.  ## Consequences  Schema validation can resolve plan-to-ADR authority, and semantic search can find the current decision edge. If a later ADR supersedes this alignment record, it must update frontmatter links on the associated plans and research notes.  ## Codification candidates  No project rule is promoted from this retrospective alignment alone.

### audit

- `2026-05-20-cli-persona-testimonials-audit` - `cli-persona-testimonials` audit: `cli-operator-persona-testimonial-audit`
- `2026-05-21-cli-persona-testimonials-audit` - `cli-persona-testimonials` audit: `errorcode-message-key-translation-gap`

### exec

- `2026-05-22-cli-persona-testimonials-P04-S01` - P04.S01 - work-unit metadata declaration inputs
- `2026-05-22-cli-persona-testimonials-P04-S02` - P04.S02 - profile bindings and estimacion-directa channel
- `2026-05-22-cli-persona-testimonials-P05-S01` - P05.S01 - profile display names and UUID identity
- `2026-05-22-cli-persona-testimonials-P05-S02` - P05.S02 - CLI UX polish cluster
- `2026-05-22-cli-persona-testimonials-P06-S04` - P06.S04 - Modelo 200 casilla 00592 registry drift
- `2026-06-30-cli-persona-testimonials-W01-P01-S01` - Inventory persona roots transcripts summaries and closeout gaps
- `2026-06-30-cli-persona-testimonials-W01-P01-S02` - Reconcile testimonial closeout ledger against the vault audit trail
- `2026-06-30-cli-persona-testimonials-W01-P01-S03` - Record the current campaign tracker as the canonical wave schedule
- `2026-06-30-cli-persona-testimonials-W01-P02-S04` - Classify shared worktree dirty files and active ownership before assignment

### plan

- `2026-05-21-cli-persona-testimonials-plan` - `cli-persona-testimonials` `cli-persona-testimonial-remediation-plan` plan
- `2026-06-30-cli-persona-testimonials-plan` - `cli-persona-testimonials` plan

### research

- `2026-05-20-cli-persona-testimonials-research` - `cli-persona-testimonials` research: `cli-i18n-naked-string-remediation-inventory`
