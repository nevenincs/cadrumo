---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S58'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# correct the especial-prorrata mandatory predicate which applies a strict greater-than where the law says exceeds by ten percent or more, so exact equality currently fails to trip a mandatory regime switch

## Scope

- `src/cadrumo/domain/iva/_prorrata.py`

## Description

- Verified the handed-over premise against the bundled corpus, the live
  consolidated law, the modifying article and the law as originally enacted,
  before changing any comparison.
- Ran the law-invariance check across the filing years the code actually
  serves, and found the provision is not invariant, which changed the shape of
  the fix.
- Located both tests that pinned the current behaviour and ruled on which side
  of each was wrong.
- Made the predicate resolve its margin and its comparison from the filing
  year, through a single typed rule the operator surfaces also read.
- Grounded the year split in the bundled corpus as required text, and recorded
  both figures with their enacting instruments at the constant declarations.
- Swept the fixed ten-percent claim out of the operator messages and the
  docstrings that repeated it, since the claim is now year-dependent.
- Proved the fix by two mutations, each flipping assertions across both the
  domain and the application layer.

## Outcome

The reported defect is real and the premise was confirmed independently, not
inherited. The provision in force reads "exceda en un 10 por ciento o mas del
que resultaria por aplicacion de la regla de prorrata especial". "O mas"
reaches the margin, so a general-regime deduction of exactly 110 against an
especial-regime deduction of 100 already obliges the especial regime. The
predicate compared strictly, so that taxpayer was not routed into the regime
the law requires. The sentence was read verbatim in the bundled consolidated
Ley 37/1992 at the article 103 block and again in the live consolidated text
fetched from the authority, and the two agree word for word.

The law-invariance check overturned the shape of the fix, and this is the
finding that matters most. Article 103, apartado Dos, number 2, has had
exactly two redactions, and the consolidated text lists both: the original,
published 29 December 1992 and in force from 1 January 1993, and the current
one, published 28 November 2014 and in force from 1 January 2015. The
amendment note names the modifying instrument precisely, and it modifies the
very subapartado this predicate reads. Reading the modifying article itself
confirms the replacement text, and reading the law as originally enacted
confirms the text it replaced: the original required the general-regime total
to exceed the especial-regime total "en un 20 por 100", with no "o mas". The
2014 preamble states the change in its own words as lowering the admissible
difference from twenty to ten percent. So the amendment moved both axes at
once: it lowered the figure and it made the comparison inclusive.

That matters because the Modelo 303 revision serving this substrate opens at
filing year 2009 and there is no minimum-supported-year floor anywhere above
it, so the served window straddles the cutover. A single year-blind predicate
is therefore wrong for part of that window no matter which figure it carries.
The pre-existing code was a hybrid of the two redactions: it took the new
ten-percent figure and kept the old exclusive comparison, so it was wrong for
every year. Correcting only the comparison operator would have left it wrong
for 2009 through 2014 by a whole factor, while making the docstring's claim to
implement the provision true only for part of its own range. The predicate now
takes the filing year and resolves the applicable redaction from it.

Both tests that pinned the old behaviour were judged wrong rather than
rewritten to match new code. The domain case table asserted that 110 against
100 was not mandatory, and the advisory test asserted the same boundary
produced no notice. Both encode the same misreading of "o mas" that produced
the defect, so both were corrected, and each now carries the immediately-below
case as a discrimination control so the assertion cannot be satisfied by a
predicate that simply answers yes. The 109.99 case stays outside the margin;
that is a 9.99 percent excess and genuinely below it.

The year split is decided in exactly one place, and the operator surfaces read
the same decision. A typed rule carries the multiple, the same threshold
expressed as the percentage the provision names, and whether reaching it
suffices. The predicate compares against the multiple; the settlement advisory
and the classify-to-enable prompt build their wording from the margin and the
inclusiveness, and both ride on the notice context as structured fields. Before
this change the advisory message already told the operator the margin was "10%
o mas" while the code applied the exclusive reading, so the prose and the
behaviour contradicted each other; they can no longer disagree, and a reader of
the envelope can tell which redaction produced the obligation. Asserting on the
context rather than on the message text also keeps the tests off localised
prose.

Grounding follows the bundled-first discipline and stops honestly where the
bundled evidence stops. The catalogue entry for article 103 now carries the
amendment note as required text, so the bundled consolidated corpus itself
proves that this subapartado was replaced by the 2014 instrument and therefore
that an earlier filing year is governed by a different text. That is the part
of the year split the bundled corpus can prove, and the registry's corpus
verification enforces it. The bundled consolidated text does not carry the
repealed twenty-percent wording, because a consolidated text carries only the
text in force, so that figure is grounded at the constant declaration on the
law as originally enacted, cited with its publication identifier and its
verbatim sentence, and corroborated by the 2014 preamble's own description of
the change. No new corpus excerpt was authored from any secondary source, and
the twenty-percent figure is deliberately not asserted by a bundled-corpus
gate, because the bundled corpus cannot honestly support that assertion.

The catalogue entry's provenance was updated honestly. Its notes now record
the two redactions, the modifying instrument, the entry into force and the
preamble's description, and its reviewer attribution states agent authorship
with the witnesses consulted and leaves the operator re-stamp pending. It was
not stamped as operator-reviewed.

The fix was proven by mutation, twice, and each mutation flipped assertions
rather than merely breaking a fixture. Restoring the strict comparison failed
four cases across both layers, and the failures name exactly the boundary: the
2015 and 2026 parametrisations of 110 against 100, the dedicated inclusive
boundary test, and the advisory's boundary firing test. Making the rule
year-blind, so the current text applies to every year, failed five cases: the
pre-2015 exclusive boundary, the case table's original-redaction rows, the
rule accessor's per-year expectations, the corpus grounding gate and the
advisory's pre-2015 behaviour. The two mutations fail disjoint-but-overlapping
sets, which is the evidence that the comparison fix and the year split are each
independently pinned.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
which includes the required-text corpus check that the new amendment-note entry
had to satisfy. The three directly affected test modules are 68 passed. The IVA
domain tree is 216 passed with workers disabled. The whole prorrata surface is
273 passed with workers disabled, re-run cleanly after the mutation windows had
closed so no result was measured against a mutated tree. The nitpicky
documentation build gate is 17 passed, which matters because this module is
autodoc'd and its docstrings gained cross-references. The generated API stub
tree reports conformant with no drift. Format and lint are clean on every
changed file, and the project type gate is silent.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so it was neither
started, restarted, reindexed nor probed. Grounding was done with ripgrep plus
whole-file reads, against the bundled corpus and against live fetches of the
consolidated law, the modifying instrument and the original publication.

Peer working state was checked before the first edit on all ten files this Step
touched, and all were clean. Between the start of the work and the commit,
peers modified four other files under the same trees; the commit named its ten
paths explicitly and the staged set was confirmed to contain only them.

One scope decision is recorded because it widened the change. The Step row
names the comparison operator, and a one-character change would have satisfied
its letter. The law-invariance evidence made that insufficient, so the
predicate gained a required filing-year argument, which is a signature change
on a public domain symbol and forced its one production caller and its tests to
pass the year. The alternative considered and rejected was to refuse for years
before the cutover, which would have converted a wrong answer into a raised
error on a filing-relevant advisory path and broken calculation for those
years outright.

One consequence is reported rather than acted on. The advisory's caller has the
filing year in hand and now passes it, but nothing constrains a future caller
from passing the year the calculation is run instead of the year the deductions
belong to. The parameter is documented as the filing year at the change site,
and the value flows from the work unit's filing year today, so the risk is
latent rather than present; a stronger guarantee would mean typing the year
distinctly, which is a broader change than this Step.
