---
generated: true
tags:
  - '#index'
  - '#m390-annual-autoconsumo-promotor-source'
date: '2026-08-16'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:78a7a85e47bd855486e1ab1c07ad63441e0d2942bc15950e3ef9e9b5e2aa208b'
related:
  - '[[2026-06-02-m390-annual-autoconsumo-promotor-source-adr]]'
  - '[[2026-06-04-m390-annual-autoconsumo-promotor-source-research]]'
---

# `m390-annual-autoconsumo-promotor-source` feature index

Auto-generated index of all documents tagged with `#m390-annual-autoconsumo-promotor-source`.

## Documents

### adr

- `2026-06-02-m390-annual-autoconsumo-promotor-source-adr` - `m390-annual-autoconsumo-promotor-source` adr: previous_filing aggregation over four quarterly M303 filings | (**status:** `accepted`)

### research

- `2026-06-04-m390-annual-autoconsumo-promotor-source-research` - `m390-annual-autoconsumo-promotor-source` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
