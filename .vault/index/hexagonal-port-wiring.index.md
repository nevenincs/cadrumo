---
generated: true
tags:
  - '#index'
  - '#hexagonal-port-wiring'
date: '2026-08-16'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:e4fa3dd4b6002caf91b47124b5ed4cf73ec381d106199c1dd7472249978a1d33'
related:
  - '[[2026-06-01-hexagonal-port-wiring-plan]]'
  - '[[2026-06-04-hexagonal-port-wiring-adr]]'
  - '[[2026-06-04-hexagonal-port-wiring-research]]'
---

# `hexagonal-port-wiring` feature index

Auto-generated index of all documents tagged with `#hexagonal-port-wiring`.

## Documents

### adr

- `2026-06-04-hexagonal-port-wiring-adr` - `hexagonal-port-wiring` adr: `warning closeout authority alignment` | (**status:** `accepted`)

### plan

- `2026-06-01-hexagonal-port-wiring-plan` - `hexagonal-port-wiring` plan

### research

- `2026-06-04-hexagonal-port-wiring-research` - `hexagonal-port-wiring` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
