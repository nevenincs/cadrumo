---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2b50deb91ad4346f642d6766fd2b0f2c2f6b0bd531e74a04cf8f366ff5b7eb5f'
step_id: 'S22'
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
     The S22 and 2026-08-07-aeat-liabilities-sanciones-plan placeholders are machine-filled by
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
     The BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 163 and 167 through 173 are all present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for the procedimiento de apremio, providencia and embargo, pointing corpus_ref at the bundled consolidated file, verified by the legal-entry evidence gate and ## Scope

- `src/cadrumo/_data/registry/aeat/legal/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 163 and 167 through 173 are all present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for the procedimiento de apremio, providencia and embargo, pointing corpus_ref at the bundled consolidated file, verified by the legal-entry evidence gate

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Cross-checked LGT art. 163 and arts. 167 through 173 against live BOE and the
  bundled corpus.
- Authored EIGHT catalogue entries in a new `lgt-procedimiento-apremio.toml`,
  one per article.
- Recorded which figures the range does and does not establish.

## Outcome

Eight entries, for the same reason S20 needed seven: one anchor per
`corpus_ref`.

These are the provisions behind the procedural situación labels AEAT prints on
its debts consulta — providencia de apremio, diligencia de embargo, crédito
incobrable — which is what makes them the right grounding for a register that
displays those states.

**Only two figures exist in the entire range**, both AGREE bundled versus live:
the six-month short-term realisability boundary in art. 169.3, and the
75 per cent ceiling on adjudication to the Hacienda Pública in art. 172.2.
Every other article is purely procedural. The file header says so, because an
author expecting an enforcement chapter to be full of numbers would otherwise go
looking for them and attach one to the wrong article.

Two such traps are named explicitly: the payment window following a notified
providencia is art. 62.5 by cross-reference and is NOT established by art. 167,
and the salary-seizure limits art. 171.3 defers to are fixed by the Ley de
Enjuiciamiento Civil, outside this law entirely.

All eight COMPLETE against live BOE; the range is contiguous with no *bis*
articles. Arts. 170 and 171 carry `effective_from` 2012-10-31 per Ley 7/2012.

Gate: both ratchets pass; clean collection.

## Notes

Six of the eight articles put their most quotable sentence INSIDE the heading
window — short articles open with their operative sentence right after the
title. Every phrase used here was chosen by measured offset rather than by
reading, and the obvious first-sentence quotes for arts. 163, 167, 169, 170, 172
and 173 were rejected for that reason. Art. 168 is short enough that only its
closing clause clears the window.

The LEC art. 607 seizure scale and the Reglamento General de Recaudación were
not reviewed; neither is cited by these entries.

Stamped under the same operator authorisation recorded on S19.
