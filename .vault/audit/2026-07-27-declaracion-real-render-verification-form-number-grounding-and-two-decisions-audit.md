---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:3add9e9cbe1a82d40c6a662acd5de9e5af5b13c282aa528345ba16d38b64aacd'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-r8-arbitration-enrollment-readiness-audit]]"
  - "[[2026-07-26-declaracion-real-render-verification-verify-declaracion-disposition-audit]]"
---

# `declaracion-real-render-verification` audit: `attacking the form_number grounding, plus M202 and verify_declaracion`

## Scope

Two tasks. First, adversarially re-derive the seven `form_number` values
`576d3b8d0a` wrote into the registry (Modelo 349's four, Modelo 180's three),
independent of that commit's own reading, and check whether Modelo 193's
three are genuinely as blocked as that commit claims. Second, research the
two open decisions named in Steps `P04.S17` (Modelo 202 reconcile enrolment)
and `P04.S18` (the disposition of `verify_declaracion`).

Report-only throughout: no registry data, production code, or test file is
modified by this pass. The semantic code index remained truncated throughout
and was not used as evidence. Method is stated beside every claim; measured
versus inferred is stated per conclusion.

## Findings

### m349-mapping-confirmed-four-for-four-including-both-flagged-uncertainties | high | measured directly against the instructions text, not against the commit message

Read `instr_mod_349.txt` directly rather than trusting `576d3b8d0a`'s reading of
it. The relevant passage, in full and unabridged:

"Casilla 01 Numero total de operadores intracomunitarios ... Casilla 02
Importe de las operaciones intracomunitarias ... Casilla 03 Numero total de
operadores intracomunitarios con rectificaciones ... Casilla 04 Importe de
las rectificaciones."

Against the registry's own casilla labels: `decl.numero-operadores` ("Numero
total de operadores intracomunitarios") matches Casilla 01 verbatim;
`decl.importe-operaciones` ("Importe de las operaciones intracomunitarias")
matches Casilla 02 verbatim; `decl.numero-rectificaciones` ("Numero total de
operadores intracomunitarios con rectificaciones") matches Casilla 03
verbatim; `decl.importe-rectificaciones` ("Importe de las rectificaciones")
matches Casilla 04 verbatim. All four `form_number` values in the commit are
correct.

Both flagged uncertainties resolve in the commit's favour. Casilla 03's full
sentence is "Numero total de operadores intracomunitarios con
rectificaciones" -- the "con rectificaciones" clause is genuinely there, not
an artefact of a short read, and it is what distinguishes Casilla 03 from
Casilla 01; mapping it to `decl.numero-rectificaciones` rather than
`decl.numero-operadores` is correct. Reading the passage at full length (no
truncation applied on this read) confirms Casilla 03's label is exactly what
is quoted above, with nothing cut off before or after "rectificaciones".

**Measured, four for four, against the instructions text directly.**

### m180-mapping-confirmed-three-for-three-with-a-genuine-label-wording-gap-worth-naming | high | measured directly; one discrepancy surfaced and reported rather than smoothed over

Read `modelo-180-ayuda-resumen-datos.html` directly (stripped of markup): "Casilla01
Numero total de perceptores relacionados ... Casilla02 Base retenciones e
ingresos a cuenta ... Casilla03 Retenciones e ingresos a cuenta." All three
`form_number` values (01, 02, 03) map to `decl.total-perceptores`,
`decl.base-total`, `decl.retenciones-total` correctly, and the registry's own
binding fragments already cited this exact passage as `required_text` before
this commit touched anything -- `decl.total-perceptores`'s binding carries
`required_text = ["Casilla01 Numero total de perceptores relacionados", ...]`
verbatim, so the citation was sitting in the registry already, unused by the
one field the guard reads.

The wording gap, named rather than smoothed: the instructions text and the
casilla's own `label` field disagree, in both directions. The instructions
say "Numero total de perceptores relacionados"; the registry `label` says
"Numero total de perceptores" (drops "relacionados"). The instructions say
"Base retenciones e ingresos a cuenta" and "Retenciones e ingresos a
cuenta"; the registry `label`s for both say "... total" (adds a word the
instructions text does not have). None of this affects the box-number
mapping -- the `required_text` citation ties each binding to its casilla by
`source_ref`, independent of the `label` field's wording -- but it is a real,
measured difference between two AEAT-derived strings describing the same
field, not an invented one.

**Measured, three for three on the mapping; one genuine wording gap
surfaced, not smoothed over.**

### m193-genuinely-blocked-confirmed-by-checking-both-bundled-documents-and-the-registry-itself | high | independently checked every candidate source, not just the one the commit named

Ran the real production `extract_pages_text` against the bundled
`modelo-193-296-nota-informativa-2025.pdf` directly (19 pages, 49008
characters of genuine extractable text, not a scanned image): zero
occurrences of "casilla" in any case. Grepped
`modelo-193-procedure.html`: zero occurrences of "casilla". Grepped every
registry TOML under Modelo 193's revision for `required_text` or `Casilla`:
the five citations present are prose descriptions of the modelo
("declaración informativa resumen anual", "sujetos obligados a retener"),
none names a box number the way Modelo 180's binding names "Casilla01 ...".

There is no source in this repository, corpus or registry, that states a
printed box number for any of Modelo 193's three affected targets. The
inference an adjacent, structurally identical form (Modelo 180 shares the
same three-target resumen shape) would tempt is exactly the inference this
line of work exists to refuse, and nothing here overrides that refusal.

**Measured: genuinely blocked, confirmed by checking every candidate source
directly rather than trusting the one document the commit cited.**

### m202-is-fully-registry-ready-and-still-not-enrollable-for-want-of-a-specimen | high | confirmed via the loaded authority, not by inference from D5 alone

Loaded the `202/2025-1P` snapshot through the real authority. All four
profile targets (`01`, `03`, `04`, `34`) resolve to real casilla definitions
with no duplicates. Of the four, exactly two (`03`, `34`) carry
`input_kind = computed` and both are correctly present in
`verification_policy().computed_casilla_ids`; the other two (`01` is
`bound`, `04` is `manual`) are correctly absent from that set, because
neither is a casilla the engine computes -- their absence is not a gap, it
is the expected shape for a non-computed input. Registry readiness (id
alignment plus verification-policy coverage of every genuinely computed
target) is therefore complete for Modelo 202, the same finding this
reviewer's earlier audit made for the other eight unenrolled modelos.

The only bundled Modelo 202 fixture (`202/2025-1P.json`) declares
`provenance = "synthetic_generated"`. No real or facsimile specimen exists.
Per D5, registry readiness is necessary but not sufficient, and a real
render is required before enrolment; Modelo 202 has the former and not the
latter. Confirms the team lead's stated expectation exactly.

**Measured: fully registry-ready, still not enrollable, for exactly the
reason D5 names.**

### the-already-corrected-docstring-now-states-the-wrong-reason-for-excluding-modelo-202 | medium | a second-order drift left by the first correction

`_DECLARATION_CASILLA_RECONCILE_MODELOS`'s docstring was corrected once
already (`5ed3c86c1e`) to stop claiming Modelo 202 has no `declaracion_pdf`
surface. Its current text now reads that Modelo 202 stays outside the
enrolled set because its "casilla-id alignment has not yet been confirmed".
That reason is itself now stale: the finding above confirms casilla-id
alignment for Modelo 202 is complete. The actual reason, per D5 (accepted
after this docstring's last edit), is that Modelo 202 has no real or
facsimile render to enrol against -- a different reason than the one
currently written down.

The docstring should read something to the effect of: "Modelo 202 ... does
carry a `declaracion_pdf` profile with confirmed casilla-id alignment, but
has no real or facsimile specimen; D5 requires one before enrolment." This
is a small, mechanical correction, and it is exactly the shape of drift this
campaign has now caught twice in the same docstring -- a true statement
overtaken by a later decision that nobody swept back through it.

### verify-declaracion-is-an-abandoned-partial-build-neither-dead-code-nor-a-deliberate-seam | high | established from an ADR and git history, cross-checked against an independent parallel audit

A parallel audit already exists under this feature
(`verify-declaracion-disposition-audit`, written by a different campaign
that found the overlap while working the reconcile surface) establishing
two facts by direct `rg` reads: no CLI entrypoint anywhere consumes
`InboundDeclaracionObservation` (the input type `verify_declaracion`
requires never arrives from an operator surface at all), and no production
package outside the `verification` package's own tests calls the function.
Re-ran both checks independently and got the same result: zero hits in
`entrypoints/` for `InboundDeclaracionObservation`, and the function's only
callers are its own test module and its package facade re-export.

Read the governing history to answer the question the docstring cannot: the
2026-04-21 `calc-verification` ADR planned this function WITH an intended
CLI wiring section, naming `aeat filing import --from-declaracion` and
`aeat filing verify <draft-id>` as the verbs that would call it. Neither verb
was ever built -- no commit anywhere introduces a `filing import` or `filing
verify` command -- and the CLI's root surface has since narrowed to `config`
and `app` only, so those planned verb names no longer fit the current
convention regardless. `_reconcile.py`'s comparison mechanism, by contrast,
is recent (its enrolment commits are all from 2026-07-02 through 07-05) and
solves a structurally different problem: it compares a filed declaration
against a persisted `CalculationRevision.casilla_values`, where
`verify_declaracion` computes fresh from supplied `binding_values` and needs
no persisted revision at all -- a genuine pre-filing check the newer
mechanism cannot perform.

This is neither "dead code" (the capability is real, distinct from both
live comparison paths, and was built to a real ADR-planned spec) nor "a
deliberate seam" (nothing anywhere states an intent to keep it dormant;
its docstring boundary claim has simply never been exercised by a caller).
The more precise description is an abandoned partial build: the comparison
half was completed and kept alive through several subsequent
restructurings, the operator-surface half of the same plan was never
built, and the CLI convention it was designed against no longer exists.
Wiring it today would mean designing a new verb under the current
`config`/`app` root and the `pull`/`file` naming standard, not resurrecting
the 2026-04 plan's literal verb names.

**Measured (no callers, no CLI consumer, confirmed independently) and
inferred (the ADR-versus-history reading of intent); both stated as such.**

## Recommendations

Task 1 found nothing wrong. All seven `form_number` values `576d3b8d0a`
wrote are correct, independently re-derived from the instructions text
rather than from that commit's own reading, including both points the team
lead specifically flagged as uncertain (the Casilla 03 "con
rectificaciones" distinction, and the un-truncated label check). Modelo
193 is confirmed genuinely blocked by checking every candidate source, not
only the one the commit named. This is a real result: a verification pass
that finds nothing wrong is not the same as one that did not try, and this
one checked the instructions text directly, the registry's own prior
citations, and the negative case (193) with equal weight.

Correct the `_DECLARATION_CASILLA_RECONCILE_MODELOS` docstring's Modelo 202
exclusion reason a second time (finding
`the-already-corrected-docstring-now-states-the-wrong-reason-for-excluding-modelo-202`):
from "casilla-id alignment has not yet been confirmed" (false; confirmed
complete) to "no real or facsimile specimen exists" (true, and the actual
D5 blocker).

Close `P04.S17` with "confirmed registry-ready, not enrollable without a
specimen" rather than leaving it open pending further investigation --
this pass found nothing further to investigate; the blocker is D3/D5
evidence, identical in shape to the other eight unenrolled modelos.

Decide `P04.S18` between enrol and delete per the parallel audit's framing,
now informed by which of the two this pass's history read supports more
strongly: enrolling means designing a CLI verb from scratch under current
naming conventions (the 2026-04 plan's verb names do not survive), not
completing a nearly-finished feature. If the product intent behind
pre-filing declaración verification is still live, that is real work
worth scoping as its own Step; if it is not, deletion is cleaner than
carrying a capability whose only claim to relevance is an eight-month-old
ADR nobody has revisited.
