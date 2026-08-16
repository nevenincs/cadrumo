---
generated: true
tags:
  - '#index'
  - '#registry-period-code-union'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:4c427c3b74dbf78a131574e6682a5bc2adb6a35c0732eae1e5b6447145818bf8'
related:
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
  - '[[2026-06-04-registry-period-code-union-research]]'
---

# `registry-period-code-union` feature index

Auto-generated index of all documents tagged with `#registry-period-code-union`.

## Documents

### adr

- `2026-06-01-registry-period-code-union-cli-boundary-adr` - `registry-period-code-union` adr: CLI-boundary period-code typing — closed-set hint vs registry-driven refusal | (**status:** `accepted`)

### research

- `2026-06-04-registry-period-code-union-research` - `registry-period-code-union` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
