---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S31'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# model M303 casilla 44 regularizacion prorrata as a computed casilla grounded in LIVA art 105-106 with the AEAT manual figure as its external oracle expectation, closing a computable value left to operator entry

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Description

- Verified the Step's premise against the loaded registry snapshot, the live
  source mesh, and the bundled BOE text before authoring anything.
- REFUSED the Step's action. Casilla 44 is not modelled as a computed casilla,
  because doing so would model one value under two mechanisms and would change
  filing output for a case the current design deliberately refuses to guess at.
- Corrected instead the stale registry comment whose false premise produced the
  finding this Step was raised from.

## Outcome

The Step is DEFERRED, not completed, and its row stays open. Every limb of its
premise was disproven against the tree.

The value is not left to operator entry. Modelo 303 casilla 44 is materialised on
the live calculate path by an enrolled source resolver. Its binding source kind is
in neither the deferred nor the reserved set, so the disposition fold classifies
it as enrolled; the staging seam runs from the bucket-aggregation calculate action
and hands the resolver the four current-year source casillas, and the resolver
returns casilla 44 as a bound input alongside the binding value.

There is a binding. The revision declares
`modelo-303-prorrata-regularizacion-casilla-44`, source `prorrata_regularizacion`,
selector output `modelo_303_casilla_44`, over the four source casillas
`iva.cuota-deducible-total`, `iva.prorrata-volumen-con-derecho`,
`iva.prorrata-volumen-total` and `iva.prorrata-porcentaje` across 1T to 4T. The
originating finding recorded no formula and no binding; the no-formula half is
right and deliberate, the no-binding half is wrong.

The formula is not expressible. LIVA art. 105.Cuatro derives the regularizacion
from the PROVISIONAL percentage and the year's cuotas soportadas. Art. 105.Uno
fixes the provisional percentage as the PRIOR year's definitive, held in the
profile-scoped prorrata register or a stamped prior-year settlement observation;
art. 105.Seis applies the percentage to the cuotas soportadas of the whole ano
natural, which for the regularised quarters is a cross-quarter cumulative sum over
prior-period observations. The loaded revision declares exactly three prorrata
casillas and no provisional-percentage casilla and no cross-quarter cumulative
deducible casilla, so neither operand is reachable by a single-period registry
formula over this revision's own casillas, bindings, relations, or parameters.

Modelling it anyway would break two standing rules and one safety property. It
would model one cross-period fold-in under two mechanisms at once, a formula and
an already-enrolled binding, which the canonical-mechanism rule exists to forbid.
It would also require the formula to produce a value when the provisional
percentage cannot be resolved; today that case produces no value and a visible
advisory naming the missing carry, so a formula would replace a loud refusal with
a silent default in a fourth-quarter settlement box.

The Step's suggested grounding is partly wrong and the correct grounding is
already present. The audit proposed LIVA articles 105 and 106. Article 106 is the
prorrata ESPECIAL regime, a different mechanism that routes each input by its
exclusive use rather than regularising a general percentage, and it is not the
basis of casilla 44. The binding provision is art. 105.Cuatro, read against
art. 105.Uno for the provisional percentage, art. 105.Seis for the base, and
art. 104 for the definitive percentage. Casilla 44 already declares
`ley-37-1992:art-104` and `ley-37-1992:art-105` and correctly omits art. 106, and
the catalogue entry for art-105 already exists at legal-authority tier with a
corpus reference into the bundled consolidated law, a document id, and required
text quoting the .Uno and .Cuatro clauses verbatim. Its notes already name
casilla 44 as the home of the regularizacion. No legal-catalogue work was needed
and none was invented.

The no-silent-under-declaration guard the finding assumed missing already exists.
The revision declares an ADVISORY verification predicate asserting that a declared
annual prorrata volume implies a non-zero casilla 44, grounded in art-104 and
art-105, so a blank box on a filing that declares annual volumes already prompts
rather than passing silently.

What was landed instead is a comment-only correction at the change site. The
predicate file stated that the binding was provisioned but casilla 44 stayed
manual until the live resolver and calculation-order seam could materialise
current-year values. Both have been in service for some time, so the text was a
stale premise sitting exactly where a reader would look, and a reviewer converted
it into a wrong finding. It now states why the casilla is deliberately
formula-less rather than pending, and names the one genuinely open question.

The open question is mechanism declaration, not computation. The casilla could
honestly declare `input_kind = "bound"` against the existing binding, so the
registry states the linkage the resolver currently makes in application code, and
so the present-source-no-value guard fires an unresolved-binding diagnostic
instead of relying on the advisory predicate alone. That is a filing-grade
behaviour change on a settlement box and a mechanism-ownership decision, which the
campaign's own review said should be ruled by a follow-on decision record rather
than settled by an executor. It is not attempted here.

Verification run: registry validation reports verified true over 73 modelos, 90
revisions, 15774 casillas and 568 legal references; the M303 and prorrata
grounding suites 177 passed; the full prorrata surface across 25 modules 178
passed. The engine chain was independently confirmed to reproduce the AEAT
manual's figures from the manual's raw givens, yielding 73 and 56 for the two
percentages, 934,40 and 716,80 for the two deductions, and -217,60 with direction
ingreso for casilla 44.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so grounding was done
with ripgrep plus whole-file reads and confirmed against the loaded registry
snapshot rather than fragment listings, per the fragmented-registry rule.

The legal text was read from the bundled consolidated law rather than any
secondary source. Article 105's five relevant clauses were extracted from the
bundled corpus file at its own anchor and quoted against the catalogue entry's
required text; article 106 was read from the same extraction and confirmed to be
the especial regime, which is what rules it out as grounding for this casilla.

Nothing in the registry's schema, predicates, formulas, bindings, or values was
changed. Only a comment was rewritten, and the registry was reloaded and
revalidated afterwards to confirm it.
