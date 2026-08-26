---
generated: true
tags:
  - '#index'
  - '#modelo-130-100-continuity'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:1d1e57da40b09b617ffc077ad163679930b9b39c17d5a1962906485b2dff4378'
related:
  - '[[2026-06-10-modelo-130-100-continuity-adr]]'
  - '[[2026-06-10-modelo-130-100-continuity-plan]]'
  - '[[2026-06-10-modelo-130-100-continuity-research]]'
  - '[[2026-07-05-modelo-130-100-continuity-audit]]'
---

# `modelo-130-100-continuity` feature index

Auto-generated index of all documents tagged with `#modelo-130-100-continuity`.

## Documents

### adr

- `2026-06-10-modelo-130-100-continuity-adr` - `modelo-130-100-continuity` adr: `Annual M100 fold-in of quarterly M130 pagos fraccionados` | (**status:** `accepted`)

### audit

- `2026-07-05-modelo-130-100-continuity-audit` - `modelo-130-100-continuity` audit: `P03 S06 review`

### exec

- `2026-06-10-modelo-130-100-continuity-P01-S01` - Research the M100 annual fold-in of M130 pagos fraccionados: identify the M100 casilla that credits pagos fraccionados ingresados, how the registry models the M130->M100 fold-in, and whether the Wave-C cross-period carry infra (filed observations + previous_filing resolver) is the mechanism or a dedicated annual aggregation is needed
- `2026-06-10-modelo-130-100-continuity-P01-S02` - Author the feature ADR deciding the M130->M100 continuity design (carry-reuse vs dedicated fold-in aggregation
- `2026-06-10-modelo-130-100-continuity-P02-S03` - Implement the fold-in: credit the four filed M130 quarterly results into the M100 annual pagos-fraccionados casilla via the decided mechanism, grounded in AEAT M100 instructions (no fabricated casilla routing)
- `2026-06-10-modelo-130-100-continuity-P02-S04` - Carry provenance + binding/persistence wiring so each credited M130 result is traceable on the M100 revision
- `2026-06-10-modelo-130-100-continuity-P03-S05` - E2E test: autonoma profile files M130 Q1-Q4 (real adapters, isolated store) then the annual M100 credits the summed pagos fraccionados in the correct casilla
- `2026-06-10-modelo-130-100-continuity-P03-S06` - Verify the annual declaration reconciles the year's advance payments and surfaces a non-silent alert on any pagos-fraccionados mismatch

### plan

- `2026-06-10-modelo-130-100-continuity-plan` - `modelo-130-100-continuity` `Annual M100 fold-in of quarterly M130 pagos fraccionados` plan

### research

- `2026-06-10-modelo-130-100-continuity-research` - `modelo-130-100-continuity` research: `M100 annual fold-in of M130 pagos fraccionados: grounding`
