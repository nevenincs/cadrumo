---
generated: true
tags:
  - '#index'
  - '#iva-autoconsumo-promotor'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-05-27-iva-autoconsumo-promotor-adr]]'
  - '[[2026-05-27-iva-autoconsumo-promotor-task-222-exec]]'
  - '[[2026-06-04-iva-autoconsumo-promotor-research]]'
---

# `iva-autoconsumo-promotor` feature index

Auto-generated index of all documents tagged with `#iva-autoconsumo-promotor`.

## Documents

### adr

- `2026-05-27-iva-autoconsumo-promotor-adr` - `iva-autoconsumo-promotor` adr: IVA autoconsumo promotor Art. 9.1.c LISIVA | (**status:** `accepted`)

### exec

- `2026-05-27-iva-autoconsumo-promotor-task-222-exec` - `task-222` M303 IVA autoconsumo promotor Art. 9.1.c LISIVA (Ramón round-24)

### research

- `2026-06-04-iva-autoconsumo-promotor-research` - `iva-autoconsumo-promotor` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
