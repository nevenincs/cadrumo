---
generated: true
tags:
  - '#index'
  - '#multi-bucket-test-fixture'
date: '2026-08-16'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:806328863db012d7b6c50113c256d8b14aae18575ab29ae39217035375f32c5f'
related:
  - '[[2026-06-03-multi-bucket-test-fixture-adr]]'
  - '[[2026-06-04-multi-bucket-test-fixture-research]]'
---

# `multi-bucket-test-fixture` feature index

Auto-generated index of all documents tagged with `#multi-bucket-test-fixture`.

## Documents

### adr

- `2026-06-03-multi-bucket-test-fixture-adr` - `multi-bucket-test-fixture` adr: `Multi-bucket test fixture for active-vs-target operator scenarios` | (**status:** `accepted`)

### research

- `2026-06-04-multi-bucket-test-fixture-research` - `multi-bucket-test-fixture` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
