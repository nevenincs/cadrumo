---
generated: true
tags:
  - '#index'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4446ca39f52d557dbb8e5c8161c26d4c4ef2717ca87ca4ff77be28ff715a09a9'
related:
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-08-07-m303-carry-reconciliation-S01]]'
  - '[[2026-08-07-m303-carry-reconciliation-S02]]'
  - '[[2026-08-07-m303-carry-reconciliation-S03]]'
  - '[[2026-08-07-m303-carry-reconciliation-S04]]'
  - '[[2026-08-07-m303-carry-reconciliation-S05]]'
  - '[[2026-08-07-m303-carry-reconciliation-S06]]'
  - '[[2026-08-07-m303-carry-reconciliation-S07]]'
  - '[[2026-08-07-m303-carry-reconciliation-S08]]'
  - '[[2026-08-07-m303-carry-reconciliation-S09]]'
  - '[[2026-08-07-m303-carry-reconciliation-S10]]'
  - '[[2026-08-07-m303-carry-reconciliation-S11]]'
  - '[[2026-08-07-m303-carry-reconciliation-S12]]'
  - '[[2026-08-07-m303-carry-reconciliation-S14]]'
  - '[[2026-08-07-m303-carry-reconciliation-S15]]'
  - '[[2026-08-07-m303-carry-reconciliation-plan]]'
  - '[[2026-08-09-m303-carry-reconciliation-s05-code-review-audit]]'
  - '[[2026-08-09-m303-carry-reconciliation-s06-code-review-audit]]'
  - '[[2026-08-09-m303-carry-reconciliation-s07-code-review-audit]]'
  - '[[2026-08-09-m303-carry-reconciliation-s08-code-review-audit]]'
---

# `m303-carry-reconciliation` feature index

Auto-generated index of all documents tagged with `#m303-carry-reconciliation`.

## Documents

### adr

- `2026-06-21-m303-carry-reconciliation-adr` - `m303-carry-reconciliation` adr: `Modelo 303 refunded period generates zero carry-forward: disposition feeds compensacion-disponible` | (**status:** `accepted`)

### audit

- `2026-08-09-m303-carry-reconciliation-s05-code-review-audit` - `m303-carry-reconciliation` audit: `S05 code review`
- `2026-08-09-m303-carry-reconciliation-s06-code-review-audit` - `m303-carry-reconciliation` audit: `M303 carry reconciliation S06 code review`
- `2026-08-09-m303-carry-reconciliation-s07-code-review-audit` - `m303-carry-reconciliation` audit: `M303 carry reconciliation S07 code review`
- `2026-08-09-m303-carry-reconciliation-s08-code-review-audit` - `m303-carry-reconciliation` audit: `M303 carry reconciliation S08 code review`

### exec

- `2026-08-07-m303-carry-reconciliation-S01` - Discover token-naming modules by AST scan instead of a hand-listed tuple, and rebind the nine surviving twin declarations to the authority
- `2026-08-07-m303-carry-reconciliation-S02` - Route the local filing path refunded rewrite through the canonical derivation and drop the contradicted formula provenance to match the sede path
- `2026-08-07-m303-carry-reconciliation-S03` - Replace the algebraically vacuous available equals posterior plus generated assertion on the resultado basis with an independent check
- `2026-08-07-m303-carry-reconciliation-S04` - Record the four deferred review findings as follow-up rows without implementing them
- `2026-08-07-m303-carry-reconciliation-S09` - Rebind the four further twin literals discovery found in the registry binding validator, which a hand-listed inventory of nine had also missed
- `2026-08-07-m303-carry-reconciliation-S10` - Add a standing real-site regression restoring an actual twin at every discovered module and confirming the verdict names it
- `2026-08-07-m303-carry-reconciliation-S11` - Establish a sound channel for recovering the filed result disposition before S05 through S08 are attempted, and record the two mis-readings that would otherwise satisfy their precondition falsely. FIRST trap. The persisted source metadata key aeat_tipo_solicitud is NOT the disposition. Its own docstring states it distinguishes an original filing from an amendment, so it is the original-versus-complementaria axis. The Spanish nouns tipo de solicitud and tipo de declaracion are near-identical and that confusion is the likely failure. SECOND trap. The justificante parser extracts only the two printed amounts, total_a_ingresar and total_a_devolver, and carries no disposition code at all. A present devolver amount identifies DEVOLUCION, but COMPENSACION and NEGATIVA both present with neither amount, and suppressing compensacion carry-forward turns on exactly that distinction, so an amounts-based inference cannot decide the case the refund gate exists to decide. Gate. The row names the channel that actually carries the code, or records that none does and that parsing the printed Tipo de declaracion is required, and a test proves COMPENSACION and NEGATIVA stay distinguishable through whichever channel is chosen rather than collapsing to one reading
- `2026-08-07-m303-carry-reconciliation-S12` - Surface the filed disposition from the parsed fichero, which already holds it. REFUSED shape, do not add casillas 72 and 73: the AEAT diseño declares 70, 71, 74, 75, 76 and 77 and not 72 or 73, our export layout carries exactly that set, and AEAT models the disposition as a HEADER at offset 13 plus sin-actividad at offset 391, so two casillas would disagree with the official structure about the concept's kind. THREE FINDINGS FROM THE FIRST WORK, recorded so they are not re-derived. ONE, the value is usable as-is: every field regardless of kind is read through _parse_field_value and appended as a ParsedExportFieldValue carrying raw, a decoded value and a source_locator, so a text header yields a decoded string and the projection change is small. TWO, parsed.fields today has exactly one consumer, _verify_submitted_file_context, which reads only DRAFT-kind fields to cross-check modelo, year and period, so every header field is parsed and discarded. THREE, and this is the blocking design question: NO sibling modelo represents a non-casilla fichero fact anywhere. ObservedCasillaValue requires a casilla_id, there is no ObservedHeaderValue or equivalent, and no observation path surfaces a header. Inventing the first such representation is a design decision to be taken deliberately and NOT settled inside a projection fix, so choose the representation before writing the projection
- `2026-08-07-m303-carry-reconciliation-S14` - 2026-08-07-m303-carry-reconciliation-S14
- `2026-08-07-m303-carry-reconciliation-S15` - 2026-08-07-m303-carry-reconciliation-S15
- `2026-08-07-m303-carry-reconciliation-S05` - DEFERRED - report a refunded basis rather than resultado once disposition recovery from the justificante Tipo de declaracion makes the branch reachable
- `2026-08-07-m303-carry-reconciliation-S06` - DEFERRED - assert the disposition-blind available reconstruction in the annual partition instead of relying on a transitive upstream rewrite in another package
- `2026-08-07-m303-carry-reconciliation-S07` - DEFERRED - refuse a persisted compensation pair where a directly filed disponible casilla overwrites available without generated following it
- `2026-08-07-m303-carry-reconciliation-S08` - IMPLEMENTED - validated observation-envelope IVA wallet recurrence

### plan

- `2026-08-07-m303-carry-reconciliation-plan` - `m303-carry-reconciliation` plan
