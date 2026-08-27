---
generated: true
tags:
  - '#index'
  - '#bucket-sealed-archive'
date: '2026-08-16'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:49096b10a7aa67d1e7d3d9d6675e0230e6cee6fedcda4786db828c5bd7ec8eda'
related:
  - '[[2026-06-03-bucket-sealed-archive-adr]]'
  - '[[2026-06-04-bucket-sealed-archive-research]]'
---

# `bucket-sealed-archive` feature index

Auto-generated index of all documents tagged with `#bucket-sealed-archive`.

## Documents

### adr

- `2026-06-03-bucket-sealed-archive-adr` - `bucket-sealed-archive` adr: `Sealed-archive format for bucket export/import` | (**status:** `superseded`)

### research

- `2026-06-04-bucket-sealed-archive-research` - `bucket-sealed-archive` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
