---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:79c2b8b0614413481dbe872a65c9646c2d1d892c64cb60514ca40292aabaf3e2'
step_id: 'S72'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# model the M303 regularizacion prorrata cuota casilla as computed with the AEAT manual figure as its external oracle expectation, the under-declaration-shape gap that fell out of tracking when its tracking step was re-scoped to other work

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Description

- Re-verified the earlier executor's refusal against the tree as it stands now,
  rather than inheriting either the refusal or the audit finding that contradicts
  it.
- Read the governing provision verbatim on the bundled consolidated law and again
  on the live authority text, and ran the amendment-history check across the
  filing years the two revisions actually serve.
- Reproduced, against the loaded registry, what the guard the refusal rests on
  does and does not cover.
- Ruled: the refusal holds, and moved the reason to the casilla declaration on
  both revisions where the next reader meets it.
- Closed the live half of the gap by mirroring the settlement advisory onto the
  older revision, which had no guard for this casilla at all.
- Rebuilt the advisory gate to discover the revisions from the registry and to
  reach each through the law-determined resolver, and proved it fails on the
  right revision by mutation.

## Outcome

**The ruling is (a): the refusal stands, and it was not durable.** Modelling the
casilla as a computed registry formula would still require inventing a value, so
the earlier executor's refusal was re-confirmed rather than overturned. What was
missing was not the modelling: it was that nothing in the registry said which of
the two contradictory records was true, and that the advisory the refusal leans
on was shipping on one revision out of two.

**The refusal was re-verified from the provisions, not from the handover.** LIVA
art. 105, apartado Cuatro, settles the definitive prorrata in the year's last
declaracion-liquidacion and requires "la consiguiente regularizacion de las
deducciones provisionales". Computing that amount needs two operands. The
provisional percentage is apartado Uno - "el porcentaje de deduccion
provisionalmente aplicable cada ano natural sera el fijado como definitivo para
el ano precedente" - the PRIOR ejercicio's definitive, which lives in the
profile-scoped encrypted prorrata register and is not a casilla of the revision.
The base is apartado Seis - "se aplicara a la suma de las cuotas soportadas por
el sujeto pasivo durante el ano natural correspondiente" - a sum across the
regularised quarters, which is not a single-period value either. A registry
formula evaluates within one period against the revision's own casillas, so
neither operand is expressible as a formula argument. Both sentences were read
verbatim in the bundled consolidated Ley 37/1992 at the article 105 block and
again in the live consolidated text fetched from the authority; the two agree
word for word, and the article heading is "Articulo 105. Procedimiento de la
prorrata general." in both, so the article has not been renumbered.

**The article named by the originating audit is the wrong one, as an earlier
pass had already established.** Article 106 is "La prorrata especial"; it governs
the per-input reglas of the especial regime and only cross-references the general
percentage. The general regularizacion is article 105, and its apartado Cuatro
specifically. That was confirmed by reading article 106 in full alongside 105.

**Law invariance was checked and comes out clean, unlike the article this
campaign checked before it.** The consolidated text records exactly one amendment
to article 105: art. 5.5 of Ley 14/2000, published 30 December 2000 and in force
from 1 January 2001, and it modifies apartado Tres alone. Apartados Uno, Cuatro
and Seis - the three the whole reasoning rests on - stand as originally enacted.
The earlier revision's window opens in 2009, after that amendment, so both
revision windows are governed by identical wording. The same amendment note
appears verbatim in the bundled corpus and in the live text.

**The premise "left to operator entry" was never the whole truth, and is less
true than the audit suggested.** The binding exists on BOTH revisions, not only
the newer one, and its resolver is enrolled on the live calculate path: the
calculation-order seam materialises the four current-year source casillas and the
resolver returns the value as a bound input for the casilla. When the provisional
carry or the current-year sources do not resolve, the resolver returns
unresolved-binding diagnostics rather than a zero. So the value is
mechanism-produced, and writing a formula would be a second mechanism for one
fold-in.

**What WAS a live defect, and is what this Step actually closes.** Reproduced
against the loaded registry before touching anything: the law-determined resolver
sends filing years 2015, 2020 and 2022 to the earlier revision and 2023, 2024 to
the newer one, and the earlier revision carried exactly ONE verification
predicate - the regimen simplificado one. Driving the predicate evaluator with a
declared annual prorrata volume of 100.000 and casilla 44 at zero returned an
ADVISORY on the newer revision and NOTHING on the earlier one. So an amended
filing for any year from 2009 to 2022 that declared annual prorrata volumes and
left the settlement casilla blank passed verify with zero findings. That is the
silent-under-declaration shape the audit named, still live, on the revision
nobody was looking at - the same single-revision blindness this campaign already
corrected twice, for the zero-volume branch and for the formula legal references.

**The mirror follows a convention the registry had already set for itself.** The
regimen simplificado guard is authored on both revisions, and the earlier
revision's copy states in its own prose that it mirrors the newer one because
both revisions carry the same manual casillas. The prorrata guard now does the
same, with the law-invariance evidence recorded at the change site so a later
reader does not repeat the amendment-history work.

**The refusal now lives where the next reader looks.** A reader who opens the
casilla declaration previously saw `input_kind = "manual"`, `required = false`,
no formula and nothing else - which is exactly the reading that produced the
audit finding. Both declarations now carry the decision: which provision governs,
which two operands it needs, why neither is a formula argument, which binding
produces the value instead, that the resolver diagnoses rather than defaults, and
where the guard lives. The reasoning previously existed only inside one
revision's verification fragment, which a reader of the casilla has no reason to
open. This matters because a prior executor had already found a stale comment on
this same casilla generating a false finding: prose that misdescribes the state
is itself the defect class here.

**Verification contract unchanged, and deliberately so.** Adding an ADVISORY
predicate does not move the verdict: the guard prompts, it does not refuse, and a
zero regularizacion stays legitimate once the operator has confirmed the carry.
The full-deduction default is untouched, confirmed by probe - a filing with the
volume antecedent at zero, and a filing with the casillas absent entirely, both
produce no finding on both revisions.

**The gate was rebuilt to be revision-complete rather than revision-keyed.** It
discovers the shipped revisions from the registry, asserts each carries exactly
one settlement advisory with its art. 104 and art. 105 grounding, and separately
reaches the revision serving a probe filing year inside each window through the
law-determined resolver, asserting the reached revision is guarded and that the
probe years reach distinct revisions. Keying on literal revision ids is what let
this survive; reaching through the resolver means a shifted window or a third
revision cannot silently reintroduce an unguarded settlement box.

**Proven by mutation, and the failure lands in the right place.** Retargeting the
new predicate away from the casilla - leaving the fragment valid and still
declaring a predicate, which is exactly the pre-change state - failed five of
six, and one of the failure messages is the defect stated outright: "2020
resolves to unguarded revision 2009-y-siguientes". The sixth, the mechanism pin,
correctly stayed green, because the mutation touched the predicate and not the
binding. That asymmetry is the evidence the gate detects this defect rather than
reacting to any change.

**One mutation is honestly reported as having proved less than it looks.** Two
further mutations - emptying the fragment, and declaring a formula on the casilla
- were both refused by registry validation before any assertion could flip, the
first as a malformed fragment and the second because the formula targets a
different casilla. So the mechanism pin's two halves are already structurally
defended at registry build, and the test is a legibility pin rather than the last
line of defence. Its docstring now says so, instead of implying a protection it
does not deliver.

**No legal-catalogue work was needed and none was invented.** Both articles
already exist in the catalogue at legal-authority tier with bundled corpus
references, BOE document identifiers and verbatim required text, and the article
105 entry's notes already describe apartado Cuatro reaching this exact casilla.
Its reviewer attribution records honest agent authorship pending operator
re-stamp and was not touched. Because no legal entry changed, the
registry-and-legal-entry atomicity constraint is satisfied trivially.

**Verification run.** Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
which includes the required-text corpus check on every legal reference; none of
those counts moved, because a predicate is not a casilla, formula or legal
reference. The rebuilt gate together with its regimen simplificado sibling is 10
passed. The prorrata and Modelo 303 surfaces across both marker lanes are 503
passed. The prorrata surface on the default lane is 249 passed. Full-tree
collect-only is 15062 collected with no collection errors. Format and lint are
clean on the changed test module.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
semantic index is broken and its service is stopped, with a standing instruction
not to start, restart, reindex or probe it. It was neither started nor probed.
Grounding was done with literal search plus whole-file reads, confirmed against
the loaded registry snapshot rather than fragment listings for every structural
claim, and against the bundled corpus plus a live fetch of the consolidated law
for the legal text. This waiver is recorded because the mandate otherwise
requires refusing the work outright.

**The commit was swept by a peer.** The four authored paths were staged with an
explicit pathspec and the staged set was confirmed to name only them. Between
staging and committing, a peer ran a commit with no pathspec and it carried all
four under its own subject and message. All four were then verified byte-identical
between the working tree and that commit, so nothing was lost and nothing of the
peer's was disturbed. No destructive recovery was attempted, and none is
appropriate: the content is at the branch head and only the attribution is wrong.
This is the second occurrence of the same hazard inside this campaign.

Peer working state was checked before the first edit on every file this Step
touched and all were clean. A peer held the index lock during staging, which was
waited out rather than cleared.

The mandatory code review has not been performed. No delegation tool was
available in this session, so the review is owed and should be dispatched by the
coordinator against the four paths this Step authored.

One observation is reported rather than acted on. The registry declares a
`bound` input kind whose contract is exactly this situation - a casilla fed by a
named binding, carrying no formula - and the casilla continues to declare
`manual` while a binding feeds it. Declaring `bound` would make the linkage
registry-stated rather than resolver-stated, but it is read at roughly twenty
production sites spanning export completeness, filing replay, the wizard input
surface and the calculate seam, so it is a filing-grade behaviour change and not
a declaration tidy-up. The verification fragment already flagged it as an open
mechanism-ownership question; it needs its own Step with the blast radius
measured, and it was deliberately not taken here.
