---
generated: true
tags:
  - '#index'
  - '#m200-export-nif-misbinding'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:890761e1c9e571e5e1373c84d96519f8fa6bf05704b333b97b9fbd50dcd538d0'
related:
  - '[[2026-08-07-m200-export-nif-misbinding-P01-S01]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P01-S02]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P01-S03]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P02-S04]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P02-S05]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P02-S06]]'
  - '[[2026-08-07-m200-export-nif-misbinding-P03-S07]]'
  - '[[2026-08-07-m200-export-nif-misbinding-adr]]'
  - '[[2026-08-07-m200-export-nif-misbinding-plan]]'
  - '[[2026-08-07-m200-export-nif-misbinding-reference]]'
---

# `m200-export-nif-misbinding` feature index

Auto-generated index of all documents tagged with `#m200-export-nif-misbinding`.

## Documents

### adr

- `2026-08-07-m200-export-nif-misbinding-adr` - `m200-export-nif-misbinding` adr: `stop binding the filer's own NIF into the grupo mercantil foreign-TIN slot` | (**status:** `accepted`)

### exec

- `2026-08-07-m200-export-nif-misbinding-P01-S01` - Re-declare field modelo-200-page-001b-draft-profile_tax_id-pos-141 as kind filler, dropping draft_attribute
- `2026-08-07-m200-export-nif-misbinding-P01-S02` - Add a byte-range regression asserting the rendered page-001b offset 141 to 155 is blank for a populated profile_tax_id draft
- `2026-08-07-m200-export-nif-misbinding-P01-S03` - Prove the new regression is load bearing by reverting the field to draft profile_tax_id, confirming the test reds, then restoring the fix
- `2026-08-07-m200-export-nif-misbinding-P02-S04` - Add a registry-build validator asserting a draft field whose draft_attribute resolves to a typed fixed-width source declares a matching length, starting with profile_tax_id against SubjectTaxId at 9 characters
- `2026-08-07-m200-export-nif-misbinding-P02-S05` - Add a fixture-anchor test mutating a scratch export field's profile_tax_id length away from 9 and asserting RegistryValidationError, then restore
- `2026-08-07-m200-export-nif-misbinding-P02-S06` - Name the new width check as the slot-width sibling of the overlap check in the module docstring
- `2026-08-07-m200-export-nif-misbinding-P03-S07` - Scaffold a research document recording the unwired grupo mercantil block and the unswept broader draft-attribute, casilla, and binding semantic-mismatch sweep as open questions for a future ADR

### plan

- `2026-08-07-m200-export-nif-misbinding-plan` - `m200-export-nif-misbinding` plan

### reference

- `2026-08-07-m200-export-nif-misbinding-reference` - `m200-export-nif-misbinding` reference: `M200 grupo mercantil NIF export field misbinding`
