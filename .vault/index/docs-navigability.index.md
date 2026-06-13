---
generated: true
tags:
  - '#index'
  - '#docs-navigability'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-01-docs-navigability-plan]]'
  - '[[2026-06-04-docs-navigability-adr]]'
  - '[[2026-06-04-docs-navigability-research]]'
---

# `docs-navigability` feature index

Auto-generated index of all documents tagged with `#docs-navigability`.

## Documents

### adr

- `2026-06-04-docs-navigability-adr` - `docs-navigability` adr: `warning closeout authority alignment` | (**status:** `accepted`)  ## Problem Statement  The vault lifecycle checks reported this feature as having execution records or a plan without an explicit same-feature ADR authority record. That weakens semantic discovery because developer briefings can find work evidence without a local decision anchor.  ## Considerations  This ADR is a curation alignment record, not a new implementation mandate. It preserves historical execution context while giving the feature a stable decision node for vault health and semantic search.  ## Constraints  The pass is vault-only. No application code, tests, registry data, or runtime behavior is changed. Body wiki-links are avoided; frontmatter related fields carry the required navigation edges.  ## Implementation  Treat the linked research record as the evidence bridge for this warning closeout. Existing plans and execution records remain historical sources; this ADR exists so the feature has an explicit authority node.  ## Rationale  A same-feature ADR avoids warning-level ambiguity in the vault graph and reduces the risk that future agents brief from orphaned execution records without an authority source.  ## Consequences  Feature lifecycle checks can resolve a local ADR for this feature. Later feature-specific decisions may supersede this curation ADR if they update frontmatter links on plans, research, and indexes.  ## Codification candidates  No project rule is promoted from this warning closeout record.

### plan

- `2026-06-01-docs-navigability-plan` - `docs-navigability` `documentation navigability cross-link campaign` plan

### research

- `2026-06-04-docs-navigability-research` - `docs-navigability` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
