---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:13241222a694bb2ab7b269d7df2d324f4d4f06a27aaa5a2d15ba09f63cf23cba'
step_id: 'S22'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

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
