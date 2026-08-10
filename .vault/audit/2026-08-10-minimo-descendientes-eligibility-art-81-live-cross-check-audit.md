---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:7f9f439b152fd32847fc35a2adaebcddadffd4084fdc8a123f95825fcc13aada'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - "[[2026-08-08-minimo-descendientes-eligibility-guarderia-cotizaciones-ceiling-adr]]"
---

# `minimo-descendientes-eligibility` audit: `LIRPF art. 81 excerpt live cross-check`

## Scope

The per-article corpus excerpt `ley-35-2006-art-81.html` and the single legal
catalogue entry that cites it, `legal."ley-35-2006:art-81"` in
`src/cadrumo/_data/registry/aeat/legal/irpf.toml`. Plan row `P04.S25` escalated
this excerpt as a two-vintage hybrid and is closed as an escalation. This audit
is the completed verification behind that escalation, run against the LIVE BOE
text rather than against the bundled files alone, so that the operator's
remaining act is a signature rather than an investigation.

**No file was modified.** The catalogue entry carries
`review_status = "reviewed"` with `reviewed_by = "operator"`, so altering its
`corpus_ref`, `effective_from` or `required_text` would silently change what
that signature covers. The prepared change is written out below instead of
applied.

Method. The article was read from the BOE open-data article endpoint through
the repository's own acquirer helpers, so redaction selection follows the
documented rule -- the maximum `fecha_vigencia` across the concatenated
redactions -- rather than position. Nothing was written to the corpus by this
check. Ten phrase probes were then run across three sources: the live text in
force, the bundled consolidated file, and the excerpt.

## Findings

### The article has three redactions and the text in force dates from 2023

The live endpoint returns exactly three: `20070101` from the original
`BOE-A-2006-20764`, `20180705` from `BOE-A-2018-9268`, and the text in force
from `20230101`, produced by `BOE-A-2022-22128`. That last identifier is the
fact the whole finding turns on, and it is the one the catalogue entry
contradicts.

### The bundled consolidated file is correct; the excerpt is not

All ten probes agree between the live text in force and the bundled
consolidated `ley-35-2006.html#a81`. The excerpt diverges on six of the ten.
Five clauses that are in the current law are missing from it, and one clause
that the current law no longer contains is present in it.

| clause | live | consolidated | excerpt |
| --- | --- | --- | --- |
| adopcion or acogimiento three-year window | yes | yes | **no** |
| death-of-mother or exclusive-custody transfer | yes | yes | **no** |
| turning-three guarderia extension | yes | yes | **no** |
| gastos de custodia definition | yes | yes | **no** |
| complemento de ayuda para la infancia exclusion | yes | yes | **no** |
| per-hijo cotizaciones and cuotas ceiling | **no** | **no** | **yes** |

### It is not merely stale, it is internally impossible

The excerpt's apartado 1 carries the POST-2023 qualifying condition -- the
prestaciones-por-desempleo alternative and the thirty-days-cotizados minimum,
both introduced by the 2023 redaction. Its apartado 2 carries the PRE-2023
structure, folding the guarderia increment into apartado 1's second paragraph
and imposing the per-hijo cotizaciones ceiling that the same 2023 redaction
removed. No single vintage of this article ever read that way. A reader cannot
repair it by choosing a date, because there is no date at which it was law.

### The entry's own metadata contradicts the text it points at

`effective_from = 2007-01-01` against a document whose apartado 1 did not exist
until 2023-01-01. `review_status = "reviewed"`, `reviewed_by = "operator"`,
`reviewed_at = 2026-05-15` over that same document. The stamp asserts that a
human confirmed a text which is internally impossible, which is why this cannot
be repaired by an agent: the correction has to be made by the party the stamp
names.

### The `required_text` gate has never discriminated anything

The three pinned phrases are `Deduccion por maternidad`,
`hijos menores de tres anos` and `1.200 euros anuales`. All three are present
in the live text in force, in the bundled consolidated file, AND in the hybrid
excerpt. They are also present in the 2007 original and the 2018 redaction. The
gate therefore passes on every vintage including the broken one. It has been
green for as long as it has existed and has never been evidence about which
text the entry points at.

This is the same defect class the grounding rule warns about, in a second form:
not an author writing both the excerpt and the phrase that validates it, but a
phrase set chosen from the parts of the article that never changed.

### Two checked plan rows implement clauses their citation does not contain

`P04.S15` implements the art. 81.1 adopcion window. `P04.S23` implements the
post-alta increment, verbatim in the current text as "la deduccion
correspondiente al mes en el que se cumpla el periodo de cotizacion de 30 dias
al que se refiere el apartado 1 anterior, se incrementara en 150 euros", which
sits in apartado 3's second paragraph. Both rows are closed. Neither clause is
in the excerpt those rows' grounding resolves to. The code is right and the
citation behind it does not carry the rule.

### The excerpt can err in BOTH directions, which is the part worth ruling on

The standing apparatus watches under-declaration. This excerpt is capable of
both. Its MISSING complemento-de-ayuda-para-la-infancia exclusion would allow
the deduction for months the law excludes, which over-claims. Its PRESENT
repealed cotizaciones ceiling would cap the deduction below entitlement, which
overpays and produces valid output, no refusal and no signal to the taxpayer.
Which direction a consumer lands in depends only on which clause it reads.

### Blast radius is one entry

The excerpt is cited by exactly one catalogue entry. Nothing else in `src`,
`dev` or the registry resolves to it. The sibling entries `ley-35-2006:art-81-2`
and `ley-35-2006:art-81-3` already route around it to the bundled consolidated
file and say so in their notes, so the repoint below makes the parent entry
consistent with siblings that already took this decision.

## Recommendations

The prepared change, for the operator to review and apply. Every element is
stated so that applying it is mechanical.

**1. Re-point `corpus_ref`** from
`corpus/normatives/html/ley-35-2006-art-81.html#a81` to
`corpus/normatives/html/ley-35-2006.html#a81`, matching what `art-81-2` and
`art-81-3` already cite. The consolidated file is bundled, is byte-verified
against the live text in force on all ten probes, and needs no acquisition.

**2. Correct `effective_from`** from `2007-01-01` to `2023-01-01`, the vigencia
of the redaction in force, and record `BOE-A-2022-22128` as the norm that
produced it. The 2007 date is not merely imprecise: it names a vintage whose
text the entry does not describe.

**3. Replace `required_text` with phrases that discriminate.** Any set drawn
from the unchanged parts of the article reproduces the current defect. Phrases
verified present in the text in force and absent from the excerpt:

- `complemento de ayuda para la infancia`
- `durante los tres anos siguientes a la fecha de la inscripcion en el Registro Civil`
- `se incrementara en 150 euros`

A fourth check is worth adding in the negative direction if the gate supports
one: the repealed `las cotizaciones y cuotas totales a la Seguridad Social`
must be ABSENT. A gate that only asserts presence cannot catch a document that
carries repealed law alongside current law, which is exactly what happened
here.

**4. Retire the excerpt file** once the repoint lands, together with its two
extracted sidecars. It has one citer and no other consumer. Leaving it in place
leaves a document that is wrong in both directions available to the next author
who greps for art. 81.

**5. Re-stamp** `reviewed_at` and `reviewed_by` as part of the same change.
This is the act no agent may perform, and it is the only element above that an
agent could not have prepared.

### What this audit deliberately does not do

It does not rule on whether the other per-article `ley-35-2006` excerpts share
the defect. Only art-81 was measured. The failure mode is general enough to be
worth a sweep -- a per-article excerpt captured at one moment cannot track a
later amendment, and nothing in the corpus records which vintage an excerpt
was taken from -- but that sweep is separate work and is not evidenced here.
