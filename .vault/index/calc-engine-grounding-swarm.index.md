---
generated: true
tags:
  - '#index'
  - '#calc-engine-grounding-swarm'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-05-16-calc-engine-grounding-swarm-audit]]'
  - '[[2026-05-31-calc-engine-grounding-restoration-S01]]'
  - '[[2026-05-31-calc-engine-grounding-restoration-S02]]'
  - '[[2026-05-31-calc-engine-grounding-restoration-S03]]'
  - '[[2026-05-31-calc-engine-grounding-restoration-S04]]'
  - '[[2026-05-31-calc-engine-grounding-restoration-S05]]'
  - '[[2026-06-04-calc-engine-grounding-swarm-adr]]'
  - '[[2026-06-04-calc-engine-grounding-swarm-research]]'
---

# `calc-engine-grounding-swarm` feature index

Auto-generated index of all documents tagged with `#calc-engine-grounding-swarm`.

## Documents

### adr

- `2026-06-04-calc-engine-grounding-swarm-adr` - `calc-engine-grounding-swarm` adr: `warning closeout authority alignment` | (**status:** `accepted`)  ## Problem Statement  The vault lifecycle checks reported this feature as having execution records or a plan without an explicit same-feature ADR authority record. That weakens semantic discovery because developer briefings can find work evidence without a local decision anchor.  ## Considerations  This ADR is a curation alignment record, not a new implementation mandate. It preserves historical execution context while giving the feature a stable decision node for vault health and semantic search.  ## Constraints  The pass is vault-only. No application code, tests, registry data, or runtime behavior is changed. Body wiki-links are avoided; frontmatter related fields carry the required navigation edges.  ## Implementation  Treat the linked research record as the evidence bridge for this warning closeout. Existing plans and execution records remain historical sources; this ADR exists so the feature has an explicit authority node.  ## Rationale  A same-feature ADR avoids warning-level ambiguity in the vault graph and reduces the risk that future agents brief from orphaned execution records without an authority source.  ## Consequences  Feature lifecycle checks can resolve a local ADR for this feature. Later feature-specific decisions may supersede this curation ADR if they update frontmatter links on plans, research, and indexes.  ## Codification candidates  No project rule is promoted from this warning closeout record.

### audit

- `2026-05-16-calc-engine-grounding-swarm-audit` - `calc-engine-grounding-swarm` audit: `Calculation engine grounding`

### exec

- `2026-05-31-calc-engine-grounding-restoration-S01` - calc-engine-grounding-restoration S01 — CRIT-1: modelo_project casilla_observations
- `2026-05-31-calc-engine-grounding-restoration-S02` - calc-engine-grounding-restoration S02 — CRIT-2: ModeloCasillaProvenance missing formula_id
- `2026-05-31-calc-engine-grounding-restoration-S03` - calc-engine-grounding-restoration S03 — CRIT-3: RegistryFiledStateDrift discards provenance
- `2026-05-31-calc-engine-grounding-restoration-S04` - calc-engine-grounding-restoration S04 — HIGH-1: modelo compare delta_rows no provenance
- `2026-05-31-calc-engine-grounding-restoration-S05` - calc-engine-grounding-restoration S05 — HIGH-2: Google Sheets calc CLI missing legal_refs/source_refs

### research

- `2026-06-04-calc-engine-grounding-swarm-research` - `calc-engine-grounding-swarm` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
