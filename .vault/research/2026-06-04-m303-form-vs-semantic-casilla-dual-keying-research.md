---
tags:
  - '#research'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:0e43e20cb4b4f0a3d21d2e16ad80b2b20c47f984e3fe109a31c99d63829b0734'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---

# `m303-form-vs-semantic-casilla-dual-keying` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
