---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - '[[2026-07-26-declaracion-real-render-verification-plan]]'
---

# `declaracion-real-render-verification` audit: `S15 form_number sourcing: a measured negative result`

> **SUPERSEDED 2026-07-27. Its central negative result is false, and seven of the
> seventeen targets were sourced twenty-eight minutes after this was written.**
>
> This record concludes that no printed box number can be sourced for any of the
> seventeen targets. The very next commit in this campaign, `1a7c2ef704`, populated
> `form_number` on seven of them — Modelo 349's four and Modelo 180's three — from
> the bundled AEAT **instructions** corpus, which this audit did not check.
> `instr_mod_349` names Casilla 01 through 04 against their labels and
> `modelo-180-ayuda-resumen-datos` names Casilla01 through 03. Modelo 180's own
> registry binding had in fact been citing that file as `required_text` since it was
> authored, so the evidence was inside the registry the entire time.
>
> What survives: Modelo 193's three targets are genuinely unsourceable, confirmed
> separately by running the real extractor over its bundled nota informativa, grepping
> its procedure HTML, and checking all five `required_text` citations in its registry
> TOMLs. Its structure being identical to Modelo 180's makes inferring 01/02/03
> tempting and inadmissible. The seven `decl.ejercicio` targets are a different and
> milder problem and were resolved as a type-coherence fix.
>
> This annotation exists because a corpus consistency sweep found the record standing
> unmarked and unreferenced, reading as a live dead end. **A negative result is the one
> kind of finding that tells a reader not to look**, so leaving it uncorrected costs
> more than a stale count would: a stale number invites re-measurement, while "this
> cannot be done" removes the reason to try. The lesson is not that the conclusion was
> careless — it was measured against the corpus tree it searched — but that a negative
> result should name the sources it checked, so the next reader can see which it did
> not.

## Scope

Evidence for plan step `P04.S15`, which asks that `form_number` be populated on
the remaining inert blank-box guards.

The step's constraint is that no number may be invented. Sourcing was attempted
against the bundled corpus, and the result is negative: **there is no printed
box number to source for any of the seventeen targets**, because the documents
those modelos are designed against do not have printed boxes.

Recorded because a negative result is the most expensive kind to rediscover, and
because the failure mode if it is rediscovered impatiently is inventing a box
number on a tax form.

Gathered by an adjacent campaign while the owning author was between sessions;
the author has since resumed and owns the step. Semantic search was unusable
throughout (the code index reported itself healthy while holding roughly 68
sections against roughly 4,546 source files), so this rests on direct reads.

## Findings

### no-printed-box-exists | high | the source documents are diseños de registro, not forms

The worklist reproduces the step exactly: filtering to the `declaracion_pdf`
surface yields **seventeen targets across nine modelos** — ten fichero-BOE
positional ranges plus seven `decl.ejercicio`.

For all nine, the bundled corpus is the *diseño de registro*. Modelo 349 reads
`147-161 Numérico IMPORTE DE LAS OPERACIONES INTRACOMUNITARIAS`; Modelo 720
reads `5-8 Numérico EJERCICIO.` Those are **character positions in a
fixed-width file**, and they are precisely what already sits in the registry's
`number` field. The word *casilla* appears in none of them.

### form-number-tracks-render-evidence | high | it is declared where a render evidenced it, and nowhere else

`form_number` is a **casilla** field, not an extraction-profile target field —
worth stating because looking for it on the targets returns zero everywhere and
reads as a tree-wide absence.

Most modelos carry the explicit comment *"form_number is not declared
individually because id == form_number for all casillas"*: the field is declared
only where the printed number **differs** from the casilla id, which is exactly
where a real render evidenced a difference. Modelo 190 declares three; the
modelos with no bundled render declare none.

So the field's population already follows render evidence precisely. The
seventeen guards are not an oversight in that pattern — they are the pattern
holding.

### inert-is-correct-here | medium | the step's premise needs qualifying, not satisfying

For a fichero-BOE-designed informativa there is no printed box, so a blank field
cannot carry a box number and the guard has nothing to assert. **Inert is the
correct state there rather than a defect.**

That makes the step as written unsatisfiable under its own constraint: it asks
for numbers that do not exist, and the only way to close it as stated would be
to invent them.

## Recommendations

Qualify the step rather than complete it. Split the seventeen: any guard whose
modelo has a bundled printed render can take a sourced `form_number`; the
fichero-BOE and `decl.ejercicio` targets record that no printed box exists and
that the guard is inert by design.

Close it with that reasoning recorded, so a later pass reading "seventeen inert
guards" does not open it again as an unfinished cleanup — which is the shape
this campaign has already had to correct elsewhere.

If any of the nine later acquires a bundled real render, its guards become
sourceable at that point. That is the condition to reopen on, and it is worth
naming in the closure so the reopening is evidence-driven rather than periodic.
