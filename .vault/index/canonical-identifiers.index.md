---
generated: true
tags:
  - '#index'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4bc948e094a00f60dee73e7d4ca83871910ec30f99193dc249f5771413ba973e'
related:
  - '[[2026-08-07-canonical-identifiers-W01-P01-S03]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S05]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S06]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S07]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S08]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S33]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S48]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S49]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S50]]'
  - '[[2026-08-07-canonical-identifiers-adr]]'
  - '[[2026-08-07-canonical-identifiers-plan]]'
  - '[[2026-08-07-canonical-identifiers-reference]]'
  - '[[2026-08-10-canonical-identifiers-expediente-provenance-adr]]'
  - '[[2026-08-10-canonical-identifiers-expediente-provenance-reference]]'
---

# `canonical-identifiers` feature index

Auto-generated index of all documents tagged with `#canonical-identifiers`.

## Documents

### adr

- `2026-08-07-canonical-identifiers-adr` - `canonical-identifiers` adr: `Canonical AEAT document-identifier taxonomy` | (**status:** `accepted`)
- `2026-08-10-canonical-identifiers-expediente-provenance-adr` - `canonical-identifiers` adr: `IVA compensation expediente provenance` | (**status:** `proposed`)

### exec

- `2026-08-07-canonical-identifiers-W01-P01-S03` - Re-read domain/invoices/_ids.py against current HEAD, alias InvoiceId from core.identity.Hex64Str, and relocate it with its consumer imports updated in the same commit
- `2026-08-07-canonical-identifiers-W02-P02-S05` - declare `IdentifierNamespace` as a closed StrEnum split into AEAT-issued and app-derived groups, each member documented with the concept it names
- `2026-08-07-canonical-identifiers-W02-P02-S06` - declare `AeatExpedienteId` at the sede-schema bound and `AeatClaveLiquidacion` and `AeatPresentationId` at their current field bounds
- `2026-08-07-canonical-identifiers-W02-P02-S07` - Retype every expediente_id model field onto AeatExpedienteId, removing the per-field repeated bound and the duplicated shape validator
- `2026-08-07-canonical-identifiers-W02-P02-S08` - Retype Deuda.clave_liquidacion onto AeatClaveLiquidacion, and retype the second bare-str clave_liquidacion on the operator-facing wire payload in the same change
- `2026-08-07-canonical-identifiers-W04-P06-S33` - retype every classified bucket_event_id/event_id pydantic model field onto the existing BucketEventId alias at the sites not already using it
- `2026-08-07-canonical-identifiers-W07-P11-S48` - document the three free-text sub-populations as a code comment on IdentifierNamespace naming representative fields for each, explicitly stating none are namespace members
- `2026-08-07-canonical-identifiers-W07-P11-S49` - author and run dev/identifier_noun_census.py, an AST sweep matching field docstrings against a noun-vocabulary heuristic independent of the original suffix heuristic
- `2026-08-07-canonical-identifiers-W07-P11-S50` - triage the second-pass sweep's findings into the existing namespace set, a new namespace, or an explicit non-identifier exclusion, recording the disposition of each

### plan

- `2026-08-07-canonical-identifiers-plan` - `canonical-identifiers` plan

### reference

- `2026-08-07-canonical-identifiers-reference` - `canonical-identifiers` reference: `AEAT identifier taxonomy census`
- `2026-08-10-canonical-identifiers-expediente-provenance-reference` - `canonical-identifiers` reference: `IVA compensation expediente provenance sites`
