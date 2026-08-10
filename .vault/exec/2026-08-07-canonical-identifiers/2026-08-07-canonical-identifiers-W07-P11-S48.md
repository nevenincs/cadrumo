---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:02f50db258165ca22259281a60a36dfecfcff57a2716fbfa6884987b28a95aa5'
step_id: 'S48'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# document the three free-text sub-populations as a code comment on IdentifierNamespace naming representative fields for each, explicitly stating none are namespace members

## Scope

- `src/cadrumo/core/identity/_namespace.py`

## Description

- Name the three free-text sub-populations beneath the namespace enum, each with representative fields, and state that none are members.

## Outcome

Delivered as part of the namespace module's own landing rather than as a later edit. The
comment sits directly beneath the enum and names all three populations the decision record
distinguishes:

- AEAT-printed adjudicated-case prose, whose vocabulary this application neither controls
  nor can enumerate, with the declaration status and debt situation fields named.
- Counterparty-issued document numbers, minted by a third party rather than by AEAT or by
  this application, with the invoice number named.
- Identifiers from non-AEAT issuing authorities, with the Google file, folder and
  spreadsheet ids, an X.509 certificate serial and an SPDX id named.

Each is stated as deliberately excluded rather than merely absent, which is the distinction
the row exists to create: a later sweep reading the enum learns that these were adjudicated
out, not overlooked.

## Notes

**Delivered ahead of its row, and the record says so rather than presenting it as executed
in sequence.** The comment was written when the enum was declared, because an enum whose
exclusions are documented three rows later is an enum that reads as complete while a
reader has no way to tell an excluded population from a forgotten one. The row is closed
against delivered content, not against work performed after it was opened.

**The framing is deliberately negative rather than definitional.** The comment does not
define what these fields are; it records that they were considered and refused. That is
the honest claim — whether any of them warrants typing under some other authority is
explicitly left open, because it is a different decision from this taxonomy's scope.
