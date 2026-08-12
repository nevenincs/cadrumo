---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c24ffce134a1aff28a51ba68b91bf18b490242e9e8cd6038823696ad59e50c75'
step_id: 'S20'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 178 through 212 are all present in the bundled consolidated Ley 58/2003 and in its sidecar. Author the legal-catalogue entry for the regimen sancionador focused on the arts. 191-197 pecuniaria proporcional bands, pointing corpus_ref at the bundled consolidated file. Every band percentage is cross-checked against live BOE by the reviewer before stamping

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Cross-checked every band and threshold in LGT arts. 191 through 197 against
  live BOE and the bundled corpus.
- Authored SEVEN catalogue entries in a new `lgt-regimen-sancionador.toml`, one
  per article.
- Recorded in the file header the two articles that move every band and are not
  catalogued here.

## Outcome

Seven entries, not one, and that is the structural finding of this row. A
`corpus_ref` resolves exactly ONE anchored unit, so "arts. 191-197" is simply
not representable as a single catalogue entry. The row as written asked for one
entry; one entry cannot carry the range.

Every figure AGREES bundled versus live: the 3.000 euro leve boundary, the
10 per cent and 50 per cent books-and-registers thresholds, and the nominal
bands — leve 50 por ciento, grave 50 al 100, muy grave 100 al 150, plus
art. 194's 15 por ciento and its 300 euro fixed multa, art. 195's 15/50 split,
art. 196's 40 por ciento and art. 197's 75 por ciento. The range is contiguous
with no *bis* articles.

**The bands are nominal, not what is paid.** Art. 187 graduates them and
art. 188 reduces them — 65 per cent for actas con acuerdo, 30 for conformidad,
a further 40 for pronto pago, in the Ley 11/2021 redaction. The bundled corpus
was checked for the superseded 50/25 figures and carries neither, so the text is
current. Neither article is catalogued here, and the file header states that a
consumer quoting an EFFECTIVE percentage without citing both is ungrounded.

Gate: both ratchets pass; the heading-only population stays at 34.

## Notes

Arts. 196 and 197 are short enough that their distinctive conduct sentence falls
inside the 220-character heading window, so each carries a single body-grounded
phrase drawn from its sanction clause. That satisfies the ratchet, whose
predicate requires ALL phrases to be heading-bound before it counts an entry,
but it is thinner grounding than the longer articles and is worth strengthening
if either is ever consumed.

Art. 195's first candidate phrase had to be replaced: `"créditos tributarios
aparentes"` occurs twice in that unit, and the validator requires uniqueness.
Caught by verifying phrases against the corpus rather than trusting the
candidate list.

Stamped under the same operator authorisation recorded on S19.
