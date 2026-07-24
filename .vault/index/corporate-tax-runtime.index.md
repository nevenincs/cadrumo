---
generated: true
tags:
  - '#index'
  - '#corporate-tax-runtime'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - '[[2026-05-26-corporate-tax-runtime-P01-S01]]'
  - '[[2026-05-26-corporate-tax-runtime-plan]]'
  - '[[2026-06-04-corporate-tax-runtime-adr]]'
  - '[[2026-06-04-corporate-tax-runtime-research]]'
---

# `corporate-tax-runtime` feature index

Auto-generated index of all documents tagged with `#corporate-tax-runtime`.

## Documents

### adr

- `2026-06-04-corporate-tax-runtime-adr` - `corporate-tax-runtime` adr: `warning closeout authority alignment` | (**status:** `accepted`)

### exec

- `2026-05-26-corporate-tax-runtime-P01-S01` - `corporate-tax-runtime` `P01.S01`

### plan

- `2026-05-26-corporate-tax-runtime-plan` - `corporate-tax-runtime` plan: IS micro-empresa bracket dispatch, INCN-gated Modelo 202 modality, new-entity period rate

### research

- `2026-06-04-corporate-tax-runtime-research` - `corporate-tax-runtime` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
