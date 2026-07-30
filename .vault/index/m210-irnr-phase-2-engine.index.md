---
generated: true
tags:
  - '#index'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
related:
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S01]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S02]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P01-S03]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S04]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S05]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P02-S06]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P03-S07]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P03-S08]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W01-P04-S09]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P05-S10]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P05-S11]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P05-S12]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P06-S13]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P06-S14]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P06-S15]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P06-summary]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P07-S16]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P07-summary]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P08-S17]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-W02-P09-S18]]'
  - '[[2026-05-27-m210-irnr-phase-2-engine-plan]]'
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

### exec

- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S01` - author the official M210 tipo-de-renta code list (01, 02, 27, 28, 29, 33, 35, ...) as declared registry data on the 2025 revision, each code row citing its bundled Orden EHA/3316/2010 and AEAT M210 instructions grounding
- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S02` - author the code-to-`TipoRentaIrnr` projection plus a registry-build parity gate that refuses at build any declared code with no mapping and any unmapped code
- `2026-05-27-m210-irnr-phase-2-engine-W01-P01-S03` - declare the official tipo-de-renta code as a typed Typer Choice at the M210 CLI boundary and add its locale keys across en/es/ca/hu through the locale CLI
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S04` - add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S05` - declare the M210 plazo windows as REGISTRY deadline_windows TOML (grounded in the bundled CONSOLIDATED Orden EHA/3316/2010 art 5, in vigor 24/06/2026 - amended by HAC/56/2024 art 4.2 + HAC/623/2026 art 1.2), NOT hand-coded in the read-only _plazo.py resolver. CURRENT LAW (supersedes the stale HAC/56/2024 January wording the earlier spec carried): a-ingresar general = 20 primeros dias de abril/julio/octubre/enero por el trimestre natural anterior (period 1T-4T)
- `2026-05-27-m210-irnr-phase-2-engine-W01-P03-S07` - FETCH-GATED (fetch: AEAT Sede "Disenos de registro - modelo 210" or the official M210 Sede form specimen) - fetch and bundle the official complete M210 field enumeration as a `layout_authority` corpus source
- `2026-05-27-m210-irnr-phase-2-engine-W01-P03-S08` - author the complete M210 casilla set on the 2025 revision with completeness manifest, extraction-profile targets, and export parity, with casilla count and numbering taken from the fetched layout authority
- `2026-05-27-m210-irnr-phase-2-engine-W01-P04-S09` - FETCH-GATED (fetch: per-treaty BOE consolidated convenio texts for FR/PT/US/NL/BE) - author tranche-1 Convenio corpus, `legal/irnr.toml` entries, and `treaties/es-XX.toml` rows keyed by `TipoRentaIrnr` with typed `ConvenioOverrideKind`, pinned by continuity parity tests
- `2026-05-27-m210-irnr-phase-2-engine-W01-P02-S06` - Author the strict Modelo 210 annual grouped-renta contract grounded in the bundled Article 2 text
- `2026-05-27-m210-irnr-phase-2-engine-W02-P05-S10` - Add the accepted M210 IRNR ledger binding source and registry selector for the gross-income target, with exclusive source ownership
- `2026-05-27-m210-irnr-phase-2-engine-W02-P05-S11` - Implement explicit persisted M210 transaction classification plus its operator write surface, runtime tipo-renta source context, Spanish-source classifier, and resolver with typed foreign, unresolved, and incomplete-classification issues
- `2026-05-27-m210-irnr-phase-2-engine-W02-P05-S12` - Add secure-store behavioural tests proving ES-only M210 aggregation, retained provenance, and source-jurisdiction/classification mutation outcomes
- `2026-05-27-m210-irnr-phase-2-engine-W02-P06-S13` - add the `source_jurisdiction` provenance pass-through on the M151 observation model
- `2026-05-27-m210-irnr-phase-2-engine-W02-P06-S14` - add the per-row segregation gate in the M151 classifier so a row with `source_jurisdiction != "ES"` produces a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation, anchored on LIRPF Art 93.5
- `2026-05-27-m210-irnr-phase-2-engine-W02-P06-S15` - add the anti-tautology test proving the Beckham IRPF base sums only the ES row, the DE row is emitted as a segregated issue with its jurisdiction preserved, and a gate-bypass mutant inflates the IRPF base by the DE row
- `2026-05-27-m210-irnr-phase-2-engine-W02-P06-summary` - `m210-irnr-phase-2-engine` `W02.P06` summary
- `2026-05-27-m210-irnr-phase-2-engine-W02-P07-S16` - architect-2 selects classifier-based vs predicate-based shape, determining the S10/S11 and S13/S14 sites (if predicate-based, author a new operator following the S376/S377/S378 pattern, otherwise close as a no-op affirming the classifier-based Steps)
- `2026-05-27-m210-irnr-phase-2-engine-W02-P07-summary` - `m210-irnr-phase-2-engine` `W02.P07` summary
- `2026-05-27-m210-irnr-phase-2-engine-W02-P08-S17` - Localize the accepted M210 source-ingestion issue reasons through the locale CLI and route calculate-time diagnostics through the canonical translation surface
- `2026-05-27-m210-irnr-phase-2-engine-W02-P09-S18` - Close cross-domain task #62 and update the source-jurisdiction ADR consequences with the verified M210 implementation commit SHAs

### plan

- `2026-05-27-m210-irnr-phase-2-engine-plan` - `m210-irnr-phase-2-engine` `M210 IRNR Phase 2 engine - full diseno-de-registro + Convenios roster + remaining tipo-de-renta variants` plan

### reference

- `2026-07-10-m210-irnr-phase-2-engine-reference` - `m210-irnr-phase-2-engine` reference: `M210 aggregation and grouped-row implementation blueprint`

### research

- `2026-06-04-m210-irnr-phase-2-engine-research` - `m210-irnr-phase-2-engine` research: `warning closeout research grounding`  ## Question  Which vault lifecycle warning needs an explicit research grounding edge so future semantic search and developer briefings do not treat execution evidence as orphaned context?  ## Findings  This note is a vault-curation closeout record. It does not introduce new runtime behavior, change an accepted architecture, or supersede an existing feature-specific research note.  The warning pass found that this feature needed an explicit research node or a plan-to-research edge. The related frontmatter carries the navigable authority chain; body wiki-links are intentionally avoided to keep body-link hygiene clean.  Semantic vault search was used before creating this bridge. Where older plan, audit, or execution records already existed, this note makes that evidence discoverable without rewriting the historical documents.  ## Recommendation  Keep this research bridge until a deeper feature-specific research record supersedes it. Any future supersession should update the related frontmatter on the linked ADR, plan, and this research record.
- `2026-07-10-m210-irnr-phase-2-engine-research` - `m210-irnr-phase-2-engine` research: `M210 grouped-rentas and ledger aggregation contract`
