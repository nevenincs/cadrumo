---
generated: true
tags:
  - '#index'
  - '#m303-synthetic-generator-primitive-spec'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9e8daa1611d0fc8c007b4c3405d662dc9e7bfe9438efd74632308e901ba83706'
related:
  - '[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]'
  - '[[2026-06-04-m303-synthetic-generator-primitive-spec-research]]'
---

# `m303-synthetic-generator-primitive-spec` feature index

Auto-generated index of all documents tagged with `#m303-synthetic-generator-primitive-spec`.

## Documents

### adr

- `2026-06-03-m303-synthetic-generator-primitive-spec-adr` - `m303-synthetic-generator-primitive-spec` adr: M303 synthetic fixture primitive box additions to _generate.py | (**status:** `accepted`)

### research

- `2026-06-04-m303-synthetic-generator-primitive-spec-research` - `m303-synthetic-generator-primitive-spec` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
