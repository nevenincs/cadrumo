---
generated: true
tags:
  - '#index'
  - '#fu-200-row-model'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:72abb37dcbfe5f070bb5fb81776c063c7234689c650e8bb1208e2200848476f5'
related:
  - '[[2026-05-27-fu-200-row-model-m349-m347-task-224-exec]]'
  - '[[2026-06-04-fu-200-row-model-adr]]'
  - '[[2026-06-04-fu-200-row-model-research]]'
---

# `fu-200-row-model` feature index

Auto-generated index of all documents tagged with `#fu-200-row-model`.

## Documents

### adr

- `2026-06-04-fu-200-row-model-adr` - `fu-200-row-model` adr: `warning closeout authority alignment` | (**status:** `accepted`)

### exec

- `2026-05-27-fu-200-row-model-m349-m347-task-224-exec` - FU-#200 — extend ModeloDetailRow union: M349 operador + M347 contraparte (Task #224)

### research

- `2026-06-04-fu-200-row-model-research` - `fu-200-row-model` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
