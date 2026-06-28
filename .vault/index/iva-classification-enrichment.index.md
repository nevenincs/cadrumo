---
generated: true
tags:
  - '#index'
  - '#iva-classification-enrichment'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-05-27-cross-domain-continuity-w05-p24-s91-s95-exec]]'
  - '[[2026-05-27-iva-classification-enrichment-adr]]'
  - '[[2026-06-04-iva-classification-enrichment-research]]'
---

# `iva-classification-enrichment` feature index

Auto-generated index of all documents tagged with `#iva-classification-enrichment`.

## Documents

### adr

- `2026-05-27-iva-classification-enrichment-adr` - `iva-classification-enrichment` adr: IVA category + counterparty enrichment on Transaction | (**status:** `accepted`)

### exec

- `2026-05-27-cross-domain-continuity-w05-p24-s91-s95-exec` - cross-domain-continuity W05.P24.S91-S95 — IVA intracom/export enrichment

### research

- `2026-06-04-iva-classification-enrichment-research` - `iva-classification-enrichment` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
