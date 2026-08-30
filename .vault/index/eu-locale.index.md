---
generated: true
tags:
  - '#index'
  - '#eu-locale'
date: '2026-08-16'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:58ed81cd513fdf26d173b39da144da1a5b84c93dbf3ca4a7f23e008e8e066ade'
related:
  - '[[2026-06-04-eu-locale-adr]]'
  - '[[2026-06-04-eu-locale-research]]'
---

# `eu-locale` feature index

Auto-generated index of all documents tagged with `#eu-locale`.

## Documents

### adr

- `2026-06-04-eu-locale-adr` - `eu-locale` adr: `warning closeout authority alignment` | (**status:** `accepted`)

### research

- `2026-06-04-eu-locale-research` - `eu-locale` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
