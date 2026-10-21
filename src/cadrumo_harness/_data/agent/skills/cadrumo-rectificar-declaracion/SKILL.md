---
name: cadrumo-rectificar-declaracion
description: >-
  Correct a declaration the taxpayer already filed: anchor on its reconciled filing
  record, agree the amendment kind (complementaria, sustitutiva or rectificativa) from
  the direction of the error, record the amendment with `aeat app modelo work amend`,
  then hand off to export. Use when a filed declaration turns out to be wrong or
  incomplete.
applies_when:
  temporal_trigger: amendment_requested
---

# Rectificar una declaración (correct a filed return)

Gating situation: a declaration the taxpayer already filed is wrong - an omitted
invoice, a misclassified movement, a figure that should have been different. The
correction path is NOT a fresh preparation: it is an amendment anchored on the filed
return, and the anchor is official evidence, not memory. Two disciplines frame it.
First, the amendment builds on a filing record that carries external AEAT evidence;
Cadrumo refuses to amend a record without it, which is a safety feature, never an
obstacle to work around. Second, the amendment KIND (complementaria when the
correction results in more in favour of AEAT, sustitutiva or rectificativa in the
other directions) is a legal classification: put the direction of the error to the
taxpayer in plain language and let the accepted kinds and the facts decide; never
guess the kind silently.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active profile).
- The declaration being corrected was filed in the AEAT portal AND its official
  evidence has been pulled - load `cadrumo-reconciliar` first if the filing record
  carries no justificante yet. An unreconciled filing cannot anchor an amendment.
- The underlying cause is corrected at its source: if the error came from the ledger,
  load `cadrumo-llevar-libro` and `cadrumo-clasificar` and fix the books BEFORE
  amending, so the corrected figures rest on corrected data.

## Procedure

1. Identify the filed record to amend with the operations `modelo.filing_record.list`
   (optionally narrowed to one modelo) and `modelo.filing_record.view` (one record by
   id); on the command line they are the `list` and `view` verbs of the `filing-record`
   group under `aeat app modelo`. Both are local reads. Confirm with the taxpayer
   which modelo, which period, what the filed figures were and what is wrong. Quote
   the filed values from the record, not from memory.
2. Establish the direction of the error in plain language: did the filed return
   declare too little in AEAT's favour (a complementaria - extra amount to pay), or
   too much or structurally wrong (the sustitutiva or rectificativa family)? Put it
   to the taxpayer as a question of what actually happened; the legal kind follows
   from the facts. For a Modelo 303 rectificativa, the motive is also required:
   `--m303-rectificativa-motive` takes `rectificaciones` or
   `discrepancia_criterio_administrativo`, and you never infer or default it.
3. Record the amendment only after the person gives the go-ahead for that exact act in
   the conversation. First say what it does: it builds a corrected revision from the
   named record, verifies it, records it locally as filed, and supersedes the record it
   corrects, so it is the same kind of act as recording the filed marker. Put the
   record, the kind, the reason and every corrected value in front of the person, then
   run once they agree to exactly that:
   `aeat app modelo work amend --from-filing-record <RECORD-ID> --kind <KIND>
   --reason <REASON> --set <CASILLA_ID=DECIMAL>` (repeat `--set` per casilla; at least
   one is required). Through the tool server it is the operation `modelo.work.amend`:
   `describe` it for its input and `execute` it. For the informative modelos with
   repeatable records, `--row` supplies the detail rows, or `--no-detail-rows` says
   there are none; omitting both is refused. The command checks its required inputs
   together and refuses with the full missing list: read the refusal, complete the
   inputs and ask the person again rather than improvising. Each `--set` is a
   casilla-level correction, and `--reason` is kept in the audit trail, so state it
   honestly.
4. Read the result: `amendment_kind`, `amends_filing_record_id` (the record it
   supersedes) and the new filing record's fields. The amendment is a new internal
   record and submits nothing to AEAT. Export it with `cadrumo-exportar-declaracion`
   once the person gives the go-ahead for that export, which is separate from the
   go-ahead for the amendment. The taxpayer files the correction in the AEAT portal
   themselves.
5. If the result carries a recargo or interest notice for the amendment, relay it verbatim;
   where a complementaria lands out of period, the past-due framing of
   `cadrumo-regularizar-atrasos` applies to the narration. Never compute a figure.
6. After the taxpayer files the amendment, load `cadrumo-reconciliar` to pull its
   official evidence like any other filing, so the corrected return carries its own
   justificante alongside the original's.

## Success assertions

- The amendment was anchored on a filing record with official evidence; none was
  attempted from an unreconciled or local-only filing.
- The amendment kind was chosen with the taxpayer from the direction of the error,
  never silently assumed.
- Every corrected figure entered via `--set` traces to a source-level fix (ledger
  correction or documented fact), and `--reason` states it.
- No narration described the amendment as filed with AEAT before the taxpayer filed it
  and `cadrumo-reconciliar` confirmed it.

## Finish

Export and reconciliation follow their own skills. This skill is done when the
corrected declaration is reconciled and the taxpayer understands what changed against
the original filing.
