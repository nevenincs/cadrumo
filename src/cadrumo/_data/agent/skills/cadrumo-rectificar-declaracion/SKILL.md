---
name: cadrumo-rectificar-declaracion
description: >-
  Life-situation itinerary for correcting an already-filed declaration:
  anchor on the filed return's official evidence, build the amendment with
  the modelo work amend surface (complementaria, sustitutiva, or
  rectificativa as the CLI accepts for the case), and drive the corrected
  filing through verification and export. Use when a declaration the
  taxpayer already filed turns out to be wrong or incomplete. Never
  chooses the amendment kind from memory; the CLI's accepted set and the
  direction of the error decide it.
applies_when:
  temporal_trigger: amendment_requested
---

# Rectificar una declaración (correct a filed return)

Gating situation: a declaration the taxpayer already filed is wrong — an
omitted invoice, a misclassified movement, a figure that should have been
different. The correction path is NOT a fresh preparation: it is an
amendment anchored on the filed return, and the anchor is official
evidence, not memory. Two disciplines frame it. First, the amendment
builds on the reconciled filing record — the CLI refuses to amend a
record without external AEAT evidence, which is a safety feature, never
an obstacle to work around. Second, the amendment KIND (complementaria
when more results in favour of AEAT, sustitutiva or rectificativa in the
other directions) is a legal classification: read the accepted set from
the CLI surface and put the direction of the error to the taxpayer in
plain language; never guess the kind silently.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile).
- The declaration being corrected was filed in the AEAT portal AND its
  official evidence has been pulled — hand off to `cadrumo-reconciliar` first if
  the filing record carries no justificante yet. An unreconciled filing
  cannot anchor an amendment.
- The underlying cause is corrected at its source: if the error came from
  the ledger, hand off to `cadrumo-llevar-libro` / `cadrumo-clasificar` and fix the books
  BEFORE amending, so the corrected calculation reads corrected data.

## Procedure

1. Identify the filed record to amend and confirm its evidence with the
   taxpayer: which modelo, which period, what the filed figures were, and
   what is wrong. Quote the filed values from the reconciled record, not
   from memory.
2. Establish the direction of the error in plain language: did the filed
   return declare too little in AEAT's favour (a complementaria — extra
   amount to pay), or too much / structurally wrong (the
   sustitutiva/rectificativa family)? Put the distinction to the taxpayer
   as a question of what actually happened; the legal kind follows from
   the facts.
3. Build the amendment:
   `aeat app modelo work amend --from-filing-record <RECORD-ID> --kind <KIND> --reason <REASON> --set <CASILLA=VALUE>`.
   The command batch-validates its required inputs and refuses with the
   full missing list — read the refusal, complete the inputs, and re-run
   rather than improvising. Each `--set` override is a casilla-level
   correction; state the reason honestly, it is part of the audit trail.
4. The amendment is a new internal filing envelope — it submits nothing to
   AEAT. Drive it through the standard verification and export: the
   verifier persona verifies, `cadrumo-exportar-declaracion` exports, and the
   taxpayer files the corrección in the AEAT portal themselves.
5. Surface any recargo or interest consequence the CLI derives for the
   amendment verbatim; where a complementaria lands out of period, the
   past-due framing of `cadrumo-regularizar-atrasos` applies to the narration —
   relay CLI figures, never compute them.
6. After the taxpayer files the amendment, `cadrumo-reconciliar` pulls its
   official evidence like any other filing, closing the loop: the
   corrected return now carries its own justificante alongside the
   original's.

## Success assertions

- The amendment anchored on a reconciled filing record with official
  evidence; no amendment was attempted from an unreconciled or
  local-only filing.
- The amendment kind was chosen with the taxpayer from the direction of
  the error and the CLI's accepted set, never silently assumed.
- Every corrected figure entered via `--set` traces to a source-level fix
  (ledger correction or documented fact), and the `--reason` states it.
- No narration described the amendment as filed with AEAT before the
  taxpayer filed it and `cadrumo-reconciliar` confirmed it.

## Hand off

Verification, export, and reconciliation follow their owning skills. This
itinerary closes when the corrected declaration is reconciled and the
taxpayer understands what changed versus the original filing.
