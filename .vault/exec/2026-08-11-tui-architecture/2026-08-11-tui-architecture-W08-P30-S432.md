---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:f7b519ab9c5286322e6308d1cb72b6d3ca3383e300b3b513112ac50a876918f4'
step_id: 'S432'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Disambiguate the repeated-number M200/2024 casillas by the record page their own id names. The record design is segmented by page headers, and a composite casilla id carries its page, so a number that repeats across pages resolves to exactly one cell without an adjudication choosing it. Validate the page selector against the shipped corpus before trusting it, corroborate each selection against the declaration's section, and hold whatever disagrees.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`

## Changes

The repeated-number casillas were reported as needing a pin to choose among
their occurrences. They do not. The record design is segmented by page headers
(`# DP200024`), and a composite casilla id carries its own page --
`DP200013:00417` IS casilla 00417 on page DP200013 -- so the number that repeats
across pages resolves to exactly one cell without anything choosing for it.

The selector was validated against the shipped corpus before being trusted. Of
3119 labelled casillas with a mapping it reproduces the shipped label exactly
2290 times, whitespace-only 145, and the shipped label is a truncation of the
selected cell 412 times: 91.3% picks the same cell. The 272 that differ are
mostly a DIFFERENT AUTHORITY rather than a miss -- the labelled corpus was built
from aeat-dr-200-2025 while these casillas cite aeat-dr-200-2024, and 00081
shows it plainly (shipped "Filial grupo multinacional o grupo nacional de gran
magnitud", 2024 design "Filial grupo multinacional"). Selecting from the 2024
design is the right authority for exactly the casillas that cite it.

38 of 40 corroborate against their declaration's section and were written. 2 are
held: DP200014B:00599 and DP200018:00588, the latter declared under
"liquidacion_iv / otras_deducciones" while its page cell reads "Deducc. para
incentivar determ.actividades - Total".

Unlabelled casillas: 54 -> 16 in es and en, 57 -> 19 in ca, 79 -> 41 in hu.

TEETH, and they are observed rather than staged. The first attempt resolved the
page from the export-field mapping instead of the casilla id, and corroboration
rejected 35 of 39 -- the mapping's page and the id's page disagree, and following
the mapping lands on "Estado de cambios patrimonio neto" for casillas declared
under "liquidacion_ii". Switching to the id's own page, the same check rejected
2 of 40. A check that refuses 35 of 39 on a wrong page and 2 of 40 on the right
one is discriminating between them, which is the property that mattered.

## Notes

STILL BLOCKED, 16 casillas. 2 do not appear in the shipped design at all; 12
have a unique occurrence their declaration contradicts (01264/01265/01266
declared "2025 innovacion tecnologica (IT)" against a design cell reading "del
Club Natacio Barcelona (CNB)", and 01683/01684/01685 declared 2026 against a
2025 cell); 2 are the page-resolved holds above. Every one is a declaration
disagreeing with its own cited authority, which is an adjudication question, not
a locale one.

The work-review screen still cannot render for M200/2024 -- one absent label is
enough, and 16 remain. The other five m200 revisions in that test pass.

These 38 labels, like the 28 before them, are grounded but carry no pin, so no
gate asserts them. 66 adjudication entries with official_label_sha256 would
bring both cohorts under the existing gate.
