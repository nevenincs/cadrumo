---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:1ebd465e977a91c7eed6ee2cb0f1faa3b83da1f8ddc6fdc520824c072cac3116'
step_id: 'S21'
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
     The S21 and 2026-08-07-aeat-liabilities-sanciones-plan placeholders are machine-filled by
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
     The BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 65 and 82 are present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for aplazamiento y fraccionamiento del pago and its garantias, pointing corpus_ref at the bundled consolidated file. Any interest rate the entry carries is cross-checked against live BOE by the reviewer before stamping and ## Scope

- `src/cadrumo/_data/registry/aeat/legal/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 65 and 82 are present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for aplazamiento y fraccionamiento del pago and its garantias, pointing corpus_ref at the bundled consolidated file. Any interest rate the entry carries is cross-checked against live BOE by the reviewer before stamping

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Scanned LGT arts. 65 and 82 exhaustively for numeric content and
  cross-checked both against live BOE.
- Authored two catalogue entries in a new `lgt-aplazamiento-garantias.toml`.
- Recorded which external norms actually fix the numbers these articles only
  frame.

## Outcome

**Neither article fixes a single number.** An exhaustive scan of both bundled
units returns zero percentages, zero amounts and zero deadlines. That is a
substantive property of these provisions rather than a gap in the review, and it
is the most useful thing this row establishes: any euro threshold or rate a
consumer states here is grounded elsewhere.

Two framing-versus-fixing cases, both recorded in the file header.

**Art. 65.4** sets a rate only by reference — "el interés legal que corresponda"
where the debt is fully secured. Interés legal and interés de demora are fixed
annually by the LPGE. No year's rate is asserted, and the header forbids adding
one to this entry.

**Art. 82.2.a** dispenses the garantía below a threshold "que se fije en la
normativa tributaria". The article frames; an Orden fixes. This is a textbook
instance of the standing rule's warning against grounding a number on the
general framework article, so the header names the Orden that carries the figure
and states that citing art. 82 alone for it would be the defect.

Both articles COMPLETE against live BOE. `effective_from` corrected per article:
2017-01-01 for art. 65 (RDL 3/2016), 2023-01-01 for art. 82 (Ley 16/2022).

## Notes

The garantía threshold figure itself is deliberately NOT written into the
art. 82 entry. It belongs to the Orden, not to the LGT, and putting it here
would be the exact mis-grounding the entry warns against — so the header names
the Orden and the number stays with whoever catalogues it.

The Reglamento General de Recaudación procedure behind both articles was not
reviewed. If a consumer reaches into that procedure it is ungrounded work.

Stamped under the same operator authorisation recorded on S19.
