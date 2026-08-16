---
generated: true
tags:
  - '#index'
  - '#profile-lifecycle-cli-cascade-supersession'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:a9b08230bb0084d5b914a1c31169cd4ee06eacd122d090063c56dc4b704c9433'
related:
  - '[[2026-06-03-profile-lifecycle-cli-cascade-supersession-adr]]'
  - '[[2026-06-04-profile-lifecycle-cli-cascade-supersession-research]]'
---

# `profile-lifecycle-cli-cascade-supersession` feature index

Auto-generated index of all documents tagged with `#profile-lifecycle-cli-cascade-supersession`.

## Documents

### adr

- `2026-06-03-profile-lifecycle-cli-cascade-supersession-adr` - `profile-lifecycle-cli-cascade-supersession` duplicate-date plan supersession ADR | (**status:** `accepted`)

### research

- `2026-06-04-profile-lifecycle-cli-cascade-supersession-research` - `profile-lifecycle-cli-cascade-supersession` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
