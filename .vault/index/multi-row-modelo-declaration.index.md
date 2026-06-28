---
generated: true
tags:
  - '#index'
  - '#multi-row-modelo-declaration'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-05-27-multi-row-modelo-declaration-adr]]'
  - '[[2026-06-04-multi-row-modelo-declaration-research]]'
---

# `multi-row-modelo-declaration` feature index

Auto-generated index of all documents tagged with `#multi-row-modelo-declaration`.

## Documents

### adr

- `2026-05-27-multi-row-modelo-declaration-adr` - `multi-row-modelo-declaration` adr: Multi-row modelo declaration mechanism | (**status:** `accepted`)

### research

- `2026-06-04-multi-row-modelo-declaration-research` - `multi-row-modelo-declaration` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
