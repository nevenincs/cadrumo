---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:25f7ecafc85d7c8d36999f6521975ec9b12dd225cf58e872f4a9c65693d6c50b'
step_id: 'S19'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half of this row's blocker is discharged as of 2026-08-10: the consolidated Ley 58/2003 is bundled with its extracted sidecar, so art. 28 is present and a corpus_ref has a target. Author the legal-catalogue entry for LGT art. 28, recargo del periodo ejecutivo and recargo de apremio, pointing corpus_ref at the bundled consolidated file at anchor a28 rather than hand-authoring a duplicate excerpt. The reviewer cross-checks every percentage against live BOE before stamping, because the standing grounding rule distrusts bundled text on a number

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Cross-checked every figure in LGT art. 28 against live BOE as well as the
  bundled consolidated corpus, and independently re-verified the bundled side.
- Authored the `ley-58-2003:art-28` catalogue entry in a new
  `lgt-recargos-periodo-ejecutivo.toml`, anchored on the bundled consolidated
  law because no per-article extraction exists for this article.
- Stamped `effective_from` at the article's real last-version vigencia rather
  than the law's original date.

## Outcome

Three rates grounded: recargo ejecutivo at cinco por ciento, recargo de apremio
reducido at 10 por ciento, recargo de apremio ordinario at 20 por ciento. All
three AGREE bundled versus live BOE, and art. 28 is the ONE subject in this
phase confirmed through two independent live channels — the BOE consolidated API
and AEAT's own published surcharge table.

Two findings the entry encodes that a careless author would have got wrong.

**The article fixes no deadline.** The reducido window is a bare cross-reference
to art. 62.5, so a deadline stated against art. 28 would be grounded on the
wrong provision. The notes say so explicitly.

**The five per cent is spelled in words.** `"5 por ciento"` does not occur in
art. 28; only `"cinco por ciento"` does. A `required_text` written with the
digit form raises on registry load — it fails closed, but it reads as a corpus
fault rather than a transcription slip, so the entry quotes the word form.

`effective_from` is 2012-01-01, not the 2004-07-01 every existing LGT entry
carries: RDL 20/2011 added apartado 6 and that is the last consolidated version.

Gates: the heading-only ratchet and the anchor-verification ratchet both pass,
six cases. Registry collection is clean.

## Notes

The catalogue schema has **no draft state**. `review_status` is a literal
`reviewed` with `reviewed_at` and `reviewed_by` both required, so an unstamped
entry cannot exist in the tree — landing the entry and stamping it are the same
action. The operator ruled explicitly on this, naming themselves the reviewer
and authorising the cross-check to be carried out by a dispatched review agent;
the entry is stamped on that authorisation, with the cross-check performed and
then independently re-verified against the bundled corpus before stamping.

The review provenance and its limitation are recorded in the file header rather
than only here, so they travel with the data.
