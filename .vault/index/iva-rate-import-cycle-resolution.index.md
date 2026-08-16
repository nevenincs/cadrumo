---
generated: true
tags:
  - '#index'
  - '#iva-rate-import-cycle-resolution'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:29f785d8d07b9da5128ee6dd0dd0cae6149a8bc7162b24b8274bb1ff3643adbb'
related:
  - '[[2026-06-02-iva-rate-import-cycle-resolution-adr]]'
  - '[[2026-06-04-iva-rate-import-cycle-resolution-research]]'
---

# `iva-rate-import-cycle-resolution` feature index

Auto-generated index of all documents tagged with `#iva-rate-import-cycle-resolution`.

## Documents

### adr

- `2026-06-02-iva-rate-import-cycle-resolution-adr` - `iva-rate-import-cycle-resolution` adr: lazy-build dicts to break iva↔invoices cycle | (**status:** `accepted`)

### research

- `2026-06-04-iva-rate-import-cycle-resolution-research` - `iva-rate-import-cycle-resolution` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
