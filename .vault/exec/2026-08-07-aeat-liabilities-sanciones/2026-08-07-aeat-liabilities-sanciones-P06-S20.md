---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:52422570cc974259e43ae6d20b8b3f2fb824701ec7c7b35b7d6331db486f83d5'
step_id: 'S20'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-liabilities-sanciones with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-08-07-aeat-liabilities-sanciones-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 178 through 212 are all present in the bundled consolidated Ley 58/2003 and in its sidecar. Author the legal-catalogue entry for the regimen sancionador focused on the arts. 191-197 pecuniaria proporcional bands, pointing corpus_ref at the bundled consolidated file. Every band percentage is cross-checked against live BOE by the reviewer before stamping and ## Scope

- `src/cadrumo/_data/registry/aeat/legal/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
