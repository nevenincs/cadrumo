---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9fb27b9da33202eae42f764786ad7bfc982aa449a7093b8aed11fb71524bd82a'
step_id: 'S37'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Confirm both grounding statements against the bundled manuals for all six
  served years before writing anything.
- Add the judicial guarda y custodia member to the relacion axis, with its
  three-statute treatment stated on the member itself.
- Retire the axis note recording the figure as unmodelled, and record in its
  place why the Art. 81.1 exclusion is a reading rather than an omission.
- Add the member to the wizard choice list and its label to all four locale
  catalogues, through the locale CLI.
- Add the member to the flag-parser and CLI help strings.
- Assert the Art. 58.1, 58.2 and 81.1 treatments, the entry surface, and the
  fact roundtrip.
- Add a test guarding the decision NOT to encode generational degree on this
  axis.
- Absorb ruff-format drift traced to this campaign's own earlier commit.

## Outcome

A carer holding guarda y custodia of a minor by resolucion judicial can now
record what they actually are. Until now that carer had no truthful value and
recorded the default -- an ordinary descendant -- which the deduccion por
maternidad admits and their real figure does not.

Three statutes reach this member three different ways, and the combination is
what makes it a member rather than a flag. Art. 58.1 assimilates it positively
and as a THIRD category, "o, fuera de los casos anteriores, a quienes tengan
atribuida por resolucion judicial su guarda y custodia", so the tranches apply.
Art. 58.2 omits it, so the entry-event window never opens. Art. 81.1 excludes
it by name.

No grandchild member, and there is now a test holding that line. Hijo, nieto
and bisnieto are one relationship type differing by generational DEGREE, not
three legal bases. Encoding degree here would bolt a second, differently-shaped
axis onto one that enumerates legal bases. The Art. 81.1 grandchild exclusion
stays a known representability gap served by an advisory.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

THE FREE PROOF WAS ONE-DIRECTIONAL, AND THIS IS THE REUSABLE PART. The Step was
verified by leaning on the existing whole-enum enumeration, on the reasoning
that a member added later defaults to contributing nothing. That is true and it
is half the story. The enumeration iterates the axis, SKIPS members that are in
the admitted set, and asserts the rest contribute zero. So it catches a member
added and left out. It is silent on the opposite error: admit the member to the
set and it moves to the skip branch, while the sibling admitted-set test asserts
it contributes twelve -- and both pass green with the exclusion gone.

The general form: an enumeration test proves the SHAPE of a rule, not the
MEMBERSHIP of any particular value in it. Membership needs its own assertion.
This Step therefore pins the exclusion directly, carrying the statutory text
beside it, so a later admission fails with the sentence that forbids it rather
than passing quietly.

EVIDENCE ON THE RECORDED TENSION, WHICH IS NOT RESOLVED. Three sentences before
the exclusion, the same section's multi-filer allocation rule names the same
population. The adopted reading is that the rule is conditional rather than a
grant, and the textual support for that is the phrase "con derecho a": the
sentence opens on contributors who are ALREADY entitled and says how to divide
an entitlement determined elsewhere. It is grammatically conditional.

That supports the reading and does not settle it. The population the sentence
enumerates is wholly non-filial -- tutelado, acogido, menor bajo guarda -- so a
drafter naming judicial guarda there plausibly expected some of it to qualify.
A conditional that can never fire for one of its listed members is odd drafting
rather than merely terse, and that oddness is unexplained by the adopted
reading. The exclusion is the more specific statement and is the one
implemented; the conservative direction is identical either way, since a member
outside the set contributes zero months.

A REJECTED READING, RECORDED BECAUSE IT IS THE ATTRACTIVE WRONG ANSWER. The
tension resolves cleanly if the allocation sentence's "guarda y custodia por
resolucion judicial" means a PARENT judicially awarded custody of their own
child -- a different referent from the exclusion's non-filial minor, in which
case the two sentences never meet. It is tempting precisely because it is tidy.
It fails: the surrounding list is non-filial throughout, so the phrase sits
among categories that are all non-filial and cannot be read as filial custody
allocation. A future reader will reach for this reading; it is written down
refuted so they do not adopt it.

SCOPE. The Step named two files and only one was touched. The second was
asserted unnecessary rather than assumed: the ordinary eligibility predicate
does not read relacion at all, so Art. 58.1 assimilation follows without a code
change, and the entry-date coherence validator already gates on the Art. 58.2
entitling set, so the new member is refused an anchor for free. Both are
asserted by tests rather than left as reasoning.

Four unnamed files were unavoidable. The wizard choice list and its four locale
catalogues, because a member no operator can select is not a modelled case; the
flag-parser docstring and the CLI help, because the advertised token set is what
an operator reads.

LOCALE HANDLING. Routed through the locale CLI, which refused the set until a
scaffold had run, so the sequence was scaffold then set, and all four catalogues
carry real translations rather than placeholders. The scaffold additionally
reflowed two UNRELATED long strings from quoted single-line to folded block
style. That is the CLI's canonical formatting rather than an edit, and it was
verified as such rather than assumed: parsing each catalogue at HEAD and after,
then comparing flattened key-value maps, showed exactly one key added per
catalogue, zero values changed and zero removed.

A REGRESSION ABSORBED BECAUSE IT WAS THIS CAMPAIGN'S OWN. The descendant-facts
module was ruff-format dirty at HEAD. The first reading was peer drift, since
that file had seen peer activity all session. Checking the parent of the
preceding commit showed it clean, which makes the drift this campaign's and not
a peer's, so it was fixed here rather than reported.

A GATE GAP, HIT FROM THE INSIDE. The exec-record gate checks that a record
EXISTS, not that it carries content. This Step read as satisfied while its
record was an empty scaffold, and the plan reported the Phase clean. The gate is
therefore not evidence that a Step is documented, only that a file was created;
a reviewer wanting the former has to open the file.

VERIFICATION. Thirty-nine tests green on the axis module. The Art. 81.1
exclusion is proven behaviourally rather than only by set membership, with
tutela and the ordinary descendant as positive controls at twelve months each,
so the gate is shown to exclude one member rather than to narrow the population.
Lanes: 1451 passed, 4 failed, 3 deselected. All four failures foreign and
attributed -- two bare modelo-code literals in a peer's relation-source
validator, and three registry-parity fixtures still expecting the title and
label keys the localization cascade removed from the Modelo 036 manifest and
revision.
