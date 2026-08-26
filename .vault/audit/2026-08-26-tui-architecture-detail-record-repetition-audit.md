---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b83d3d1c0cf20c0e0c451dd10c4540120c59182a96b79bb44bebef6e9aed6d81'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `Detail records that cannot express more than one occurrence`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Detail records that cannot express more than one occurrence | {level} | {summary}

     followed by a paragraph carrying the detail. Detail records that cannot express more than one occurrence is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

## Ruling

Modelo 184, 185 and 347 publish fixed-width export layouts whose type-2 detail
records carry no repetition declaration and are modelled as single-occurrence
casilla fields. Each of those ficheros can express exactly one detail row. A
declaration with two socios, two declarados or two inmuebles cannot be
represented at all.

This is the defect modelo 296 already carries a fix for, and its mapping states
the reasoning in place: "One record is one perceptor. Without this the layout
holds exactly one payee and a 296 with two cannot be expressed at all."

## Grounding

The AEAT disenos de registro under
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/` are explicit that
these records repeat.

- Modelo 184: "1 y tantos registros del tipo 2 como claves y subclaves
  declaradas por la entidad y declaradas por cada socio, heredero, comunero o
  participe", and "Se consignara un registro por cada clave o subclave de
  rendimientos, deducciones o ...". Both the entidad and socio records repeat.
- Modelo 347: "1 y tantos registros del tipo 2 como declarados e inmuebles
  tenga la declaracion". Both the declarado and inmueble records repeat.
- Modelo 185: the type-1 header carries "el numero total de declarados para
  este declarante (Numero de registros tipo 2)". A count field over type-2
  records is only meaningful if they repeat.

## Affected declarations

Nine record declarations across the semantic mappings under
`dev/registry/mappings/`, all published into the registry export trees:

- 184 design epochs 2023 and 2025: entidad, socio
- 347 design epochs 2011 and 2025: declarado, inmueble
- 185 design epoch 2026: declarado

Modelo 296 declares `repeat = "projection_rows"` on all four of its detail
records. Modelo 303 declares it on regimen-simplificado. No other mapping
declares repetition.

## Why the fix is not a marker

The marker cannot simply be added. The semantic map permits only
`repeat = "projection_rows"`, and registry validation refuses a record that
declares it without projection fields: "export record repeats projection rows
but has no projection fields".

Modelo 296's perceptor record carries forty-four `kind = "projection"` entries.
Modelo 184's socio record carries twenty-seven `kind = "casilla"` entries, which
address one socio's boxes rather than a row source. Correcting these means
remodelling each detail record onto a projection, as 296 was, and republishing
through the generated export tree pipeline, never a hand render.

## Status

`W03.P20.S289` is left open. Its audit clause is answered here and its premise
partly corrected below; its correction clause is real remodelling work.

## Plan-versus-code discrepancies in the row

The row cites the 232 layout as carrying the repeat marker. Modelo 232 has no
export layout declarations at all. The row also cites an M210 agrupacion record;
modelo 210's records are pages (Pagina 01, Pagina 02) with no agrupacion detail
record. The genuinely affected modelos are 184, 185 and 347.
