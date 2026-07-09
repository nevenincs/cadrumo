---
generated: true
tags:
  - '#index'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S01]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S02]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S03]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S04]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S05]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S06]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-plan]]'
  - '[[2026-06-04-m210-irnr-phase-2-engine-adr]]'
  - '[[2026-06-04-m210-irnr-phase-2-engine-research]]'
  - '[[2026-07-09-m210-irnr-phase-2-engine-adr]]'
---

# `m210-irnr-phase-2-engine` feature index

Auto-generated index of all documents tagged with `#m210-irnr-phase-2-engine`.

## Documents

### adr

- `2026-06-04-m210-irnr-phase-2-engine-adr` - `m210-irnr-phase-2-engine` adr: `warning closeout authority alignment` | (**status:** `accepted`)  ## Problem Statement  The vault lifecycle checks reported this feature as having execution records or a plan without an explicit same-feature ADR authority record. That weakens semantic discovery because developer briefings can find work evidence without a local decision anchor.  ## Considerations  This ADR is a curation alignment record, not a new implementation mandate. It preserves historical execution context while giving the feature a stable decision node for vault health and semantic search.  ## Constraints  The pass is vault-only. No application code, tests, registry data, or runtime behavior is changed. Body wiki-links are avoided; frontmatter related fields carry the required navigation edges.  ## Implementation  Treat the linked research record as the evidence bridge for this warning closeout. Existing plans and execution records remain historical sources; this ADR exists so the feature has an explicit authority node.  ## Rationale  A same-feature ADR avoids warning-level ambiguity in the vault graph and reduces the risk that future agents brief from orphaned execution records without an authority source.  ## Consequences  Feature lifecycle checks can resolve a local ADR for this feature. Later feature-specific decisions may supersede this curation ADR if they update frontmatter links on plans, research, and indexes.  ## Codification candidates  No project rule is promoted from this warning closeout record.
- `2026-07-09-m210-irnr-phase-2-engine-adr` - `m210-irnr-phase-2-engine` adr: `Phase 2 registry design, grounding strategy, and slice decomposition` | (**status:** `proposed`)

### exec

- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S01` - author the official M210 tipo-de-renta code list (01, 02, 27, 28, 29, 33, 35, ...) as declared registry data on the 2025 revision, each code row citing its bundled Orden EHA/3316/2010 and AEAT M210 instructions grounding
- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S02` - author the code-to-`TipoRentaIrnr` projection plus a registry-build parity gate that refuses at build any declared code with no mapping and any unmapped code
- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S03` - declare the official tipo-de-renta code as a typed Typer Choice at the M210 CLI boundary and add its locale keys across en/es/ca/hu through the locale CLI
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S04` - add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S05` - declare the M210 plazo windows as REGISTRY deadline_windows TOML (grounded in the bundled CONSOLIDATED Orden EHA/3316/2010 art 5, in vigor 24/06/2026 - amended by HAC/56/2024 art 4.2 + HAC/623/2026 art 1.2), NOT hand-coded in the read-only _plazo.py resolver. CURRENT LAW (supersedes the stale HAC/56/2024 January wording the earlier spec carried): a-ingresar general = 20 primeros dias de abril/julio/octubre/enero por el trimestre natural anterior (period 1T-4T)
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S06` - author the grouping-validity verification predicates (same code, same pagador save codigo 35, same tipo de gravamen, same bien, no offsetting between grouped rentas) grounded in the bundled Articulo cuarto text

### plan

- `2026-05-27-m210-irnr-phase-2-engine-plan` - `m210-irnr-phase-2-engine` `M210 IRNR Phase 2 engine - full diseno-de-registro + Convenios roster + remaining tipo-de-renta variants` plan

### research

- `2026-06-04-m210-irnr-phase-2-engine-research` - `m210-irnr-phase-2-engine` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
