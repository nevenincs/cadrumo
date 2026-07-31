---
generated: true
tags:
  - '#index'
  - '#non-resident-axis'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
body_hash: 'sha256:f76acc56712b85ced81b0a37d6658776606ecb806fb298fa43e688a535efe80a'
related:
  - '[[2026-05-27-non-resident-axis-S01]]'
  - '[[2026-05-27-non-resident-axis-S02]]'
  - '[[2026-06-04-non-resident-axis-adr]]'
  - '[[2026-06-04-non-resident-axis-research]]'
---

# `non-resident-axis` feature index

Auto-generated index of all documents tagged with `#non-resident-axis`.

## Documents

### adr

- `2026-06-04-non-resident-axis-adr` - `non-resident-axis` adr: `warning closeout authority alignment` | (**status:** `accepted`)

### exec

- `2026-05-27-non-resident-axis-S01` - non-resident-axis S01 — FiscalResidency + country_of_fiscal_residence + ue_eee_status
- `2026-05-27-non-resident-axis-S02` - `non-resident-axis` `S02`

### research

- `2026-06-04-non-resident-axis-research` - `non-resident-axis` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
