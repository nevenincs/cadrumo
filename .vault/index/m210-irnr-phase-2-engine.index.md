---
generated: true
tags:
  - '#index'
  - '#m210-irnr-phase-2-engine'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:3ea1200f60e9d49c1f52fbc6390241e7a1b9e423c208e7f318a6c5ad36018a4b'
related:
  - '[[2026-06-04-m210-irnr-phase-2-engine-research]]'
  - '[[2026-07-09-m210-irnr-phase-2-engine-adr]]'
  - '[[2026-07-10-m210-irnr-phase-2-engine-adr]]'
  - '[[2026-07-10-m210-irnr-phase-2-engine-audit]]'
  - '[[2026-07-10-m210-irnr-phase-2-engine-reference]]'
  - '[[2026-07-10-m210-irnr-phase-2-engine-research]]'
---

# `m210-irnr-phase-2-engine` feature index

Auto-generated index of all documents tagged with `#m210-irnr-phase-2-engine`.

## Documents

### adr

- `2026-07-09-m210-irnr-phase-2-engine-adr` - `m210-irnr-phase-2-engine` adr: `Phase 2 registry design, grounding strategy, and slice decomposition` | (**status:** `superseded`)
- `2026-07-10-m210-irnr-phase-2-engine-adr` - `m210-irnr-phase-2-engine` adr: `M210 grouped-rentas and source-scope ingestion` | (**status:** `accepted`)

### audit

- `2026-07-10-m210-irnr-phase-2-engine-audit` - `m210-irnr-phase-2-engine` audit: `plan reconciliation`

### reference

- `2026-07-10-m210-irnr-phase-2-engine-reference` - `m210-irnr-phase-2-engine` reference: `M210 aggregation and grouped-row implementation blueprint`

### research

- `2026-06-04-m210-irnr-phase-2-engine-research` - `m210-irnr-phase-2-engine` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
- `2026-07-10-m210-irnr-phase-2-engine-research` - `m210-irnr-phase-2-engine` research: `M210 grouped-rentas and ledger aggregation contract`
