---
generated: true
tags:
  - '#index'
  - '#m200-export-envelope-tag'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:0f7070244cf520fc0b31d55357e0ba76cf365077fca5c6b6511b82ce01f5dfa7'
related:
  - '[[2026-08-08-m200-export-envelope-tag-adr]]'
  - '[[2026-08-08-m200-export-envelope-tag-plan]]'
  - '[[2026-08-08-m200-export-envelope-tag-reference]]'
---

# `m200-export-envelope-tag` feature index

Auto-generated index of all documents tagged with `#m200-export-envelope-tag`.

## Documents

### adr

- `2026-08-08-m200-export-envelope-tag-adr` - `m200-export-envelope-tag` adr: `reconstruct the M200 fichero-BOE envelope open/close tags` | (**status:** `accepted`)

### exec

- `2026-08-08-m200-export-envelope-tag-P01-S01` - write a byte-level test asserting the M200 open-tag composite against current output, confirmed red
- `2026-08-08-m200-export-envelope-tag-P01-S02` - replace the offset-1 filing_year draft field with the six-component open-tag composite
- `2026-08-08-m200-export-envelope-tag-P01-S03` - promote the AUX and header filler fields to literal and header kind
- `2026-08-08-m200-export-envelope-tag-P01-S04` - add the envelope-footer export fragment reusing the existing computed closing-tag key
- `2026-08-08-m200-export-envelope-tag-P01-S05` - confirm the byte-level test goes green for both the open tag and the close tag
- `2026-08-08-m200-export-envelope-tag-P01-S09` - add a closed-set guard test asserting no accounts-regime concept (aseguradora, entidad de credito, inversion colectiva, garantia reciproca, estado de cuentas) exists anywhere in the registry or domain model outside an explicit allowlist, so a future addition fails the gate until both hardcoded discriminante literal '0' sites are revisited together
- `2026-08-08-m200-export-envelope-tag-P02-S06` - after P01 lands, flip the filing_year and period_code canonical-width gate abstentions to 4 and 2, rewriting the abstention comments to state what is now established
- `2026-08-08-m200-export-envelope-tag-P02-S07` - run the fichero-BOE parity and completeness gates for M200 and confirm they stay green after the restructuring
- `2026-08-08-m200-export-envelope-tag-P02-S08` - prove the byte-level test is load bearing by reverting the open-tag composite and the envelope-footer record, confirming the test reds, then restoring the fix

### plan

- `2026-08-08-m200-export-envelope-tag-plan` - `m200-export-envelope-tag` plan

### reference

- `2026-08-08-m200-export-envelope-tag-reference` - `m200-export-envelope-tag` reference: `M200 fichero-BOE envelope tag reconstruction grounding`
