---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:78b6cc0de47aa1ec7bb32ed3fd99edae6cda4968bd68a6d2a1cb41c25b6e84e3'
related:
  - "[[2026-08-12-aeat-export-fragment-generator-authority-dp30302-projection-declaration-deficit-audit]]"
  - '[[2026-08-08-aeat-design-relayout-boundary-plan]]'
---

# `aeat-export-fragment-generator-authority` reference: `m303 2023 epoch semantic home assignments`

## Summary

This is the reviewed semantic-home assignment for every non-simplified anchor of the Modelo 303
2023 design epoch, produced ahead of the map-authoring row so the reviewed judgements survive the
session that made them. It is an input to authoring, not the authored artefact: the map fragments
themselves cannot be written until the simplified-regime residue has declared endpoints, because
a map that omits an anchor is refused.

Anchors were loaded through the shipped parser against the hash-pinned official binary for the
epoch. Casilla identities were resolved through the loaded snapshot via the validated registry
authority, never from a directory listing and never from the withdrawn manual export tree.

The single most useful fact for anyone sizing the remaining work, stated up front because the raw
counts imply the opposite: across all five epochs there is exactly ONE genuine semantic-home move,
the complementaria-to-rectificativa transition at 2024-late. A reader seeing the anchor count run
from 393 to 417 will reasonably assume the family drifts, and it does not. Every other difference
between adjacent epochs is an addition, a retirement, or a total-formula growing to enumerate a tier
that arrived. The homes themselves are stable. That changes how the remaining authoring should be
sized: it is five nearly-identical maps with a short, enumerated list of deltas, not five
independent authoring jobs.

The corollary is that reuse across epochs is safe for semantic homes and UNSAFE for total formulas
and for anchor multiplicity, which is the opposite of what a casual reading would suggest.

## Counts and reconciliation

The epoch carries 393 fixed-record anchors plus 13 DP30300 prefix anchors, 406 in total, which is
the count the campaign's census row already contracts.

Of the 393 fixed anchors, 258 are non-simplified and are assigned here, with ZERO unresolved. The
remaining 135 are the DP30302 simplified-regime residue and are deliberately untouched: they are
blocked behind the projection-declaration deficit recorded in the companion audit. The 13 prefix
anchors belong to the separate variable-envelope composition contract and are out of scope here.

The 258 assigned anchors resolve as follows.

| Assignment kind | Count |
| --- | --- |
| casilla | 113 |
| projection, numbered (prorrata and differentiated ranges) | 61 |
| projection, exonerado-390 | 13 |
| literal, source-declared constant | 30 |
| filler, reserved run | 9 |
| producer, draft or computed | 32 |
| **total** | **258** |

258 assigned plus 135 simplified equals 393 fixed anchors, and 393 plus 13 prefix equals 406.

The projection arithmetic closes independently and is the strongest check available here. The 61
numbered projections plus the 13 exonerado projections give 74 projection anchors assigned. The
revision declares 108 projection endpoints. The difference is exactly 34, which is precisely the
simplified-endpoint set that remains blocked. Those two numbers were derived from opposite
directions, one by walking parser anchors and one by reading the revision's declaration index, and
they meet. That confirms both that projections have not been over-assigned and that the blocked
residue is exactly the simplified 34.

## The heuristic lesson

The first mechanical pass classified 45 anchors as producer or draft. Thirteen of those were
wrong: DP30304 ordinals 6 through 18 are the exonerado-390 block, six activity slots of a
3-character activity code plus a 4-character IAE epígrafe, followed by one 1-character trailing
field. That is 12 plus 1, matching the revision's 12 activity endpoints and 1
operaciones-con-terceros endpoint exactly. They are projections, not header producers.

The failure mode is the reusable part, and it is stated here in the form the next author needs:
the heuristic treated "no bracket in the description" as meaning "not a projection", when the real
test is whether the revision DECLARES an endpoint for that anchor. Description shape is a proxy;
endpoint declaration is the fact.

Had the 258 been run as a batch because they were unblocked, thirteen live exonerado fields would
have been bound to the wrong payload axis and would still have bijected cleanly against parser
output. A clean bijection over wrong homes is the silent under-declaration shape this campaign
exists to prevent, and no mechanical validator in the pipeline would have caught it.

## Numbered anchor resolution

Two rules govern numbered anchors and both were established the hard way, as the companion audit's
three successive corrections record.

The field's own official box is the TRAILING bracket in its description. Earlier brackets are
formula operands. Twelve fields in this epoch carry more than one bracket and each was checked
individually rather than trusted to the rule. All twelve resolve correctly, including an
eighteen-bracket exonerado total that correctly yields box 88, a fourteen-bracket total cuota
devengada that yields 27, an eleven-bracket total a deducir that yields 45, and a conditional
"Si 1T, 2T, 3T" DP30302 total whose formula repeats operands and still correctly yields 54.

Resolve the box against casilla `number` first and `form_number` second, treating neither alone as
authoritative.

DP30301 ordinal 79 deserves its own note, because the next author WILL meet it and needs to know it
is the known-hard case rather than an anomaly to be worked around. Its description reads as the
general-regime result computed from boxes 27 and 45, ending in its own box 46. It is the only
anchor in the entire epoch that needs the `form_number` fallback at all, resolving to
`iva.resultado-regimen-general`, whose `number` degenerately repeats its own id.

That single field exercises BOTH halves of the resolution rule at once: take the trailing bracket
rather than an operand, then fall back from `number` to `form_number`. It is exactly the field that
defeated three successive earlier measurements of this surface, each of which concluded the box was
missing when it was declared all along. The rule stated above is therefore validated on the precise
case that generated it, rather than asserted in the abstract, which is why it should be trusted
here and why this field is not evidence of a defect.

Anyone who finds this anchor apparently unresolvable has almost certainly matched the first bracket
instead of the last, or resolved against `number` alone. Neither is a registry problem.

## Confident assignments

Taxpayer identity resolves to the taxpayer tax-id producer, and the combined
apellidos-y-nombre-o-razón-social field to the taxpayer full-name producer, since the one official
field serves both natural persons and entities. Ejercicio and período resolve to the filing-year
and period-code draft attributes. Tipo de declaración resolves to the filing result-disposition
producer.

The DP30301 identification flags map one-for-one onto the closed producer vocabulary: foral
taxation, REDEME enrolment, joint return election, cash-accounting enrolment and its recipient
variant, special-prorrata option and revocation, the three insolvency producers covering
declaration, judicial-order date and filing subtype, voluntary SII enrolment, and exonerado-390
applicability.

The DP303DID block maps onto the selected-account producers for SWIFT-BIC, IBAN, bank name, bank
address, bank city and country code, with the SEPA marker resolving to the SEPA computed key.

DP30303's complementaria flag and prior-receipt number map to the amendment-evidence producers for
complementaria status and original AEAT receipt.

The 30 literals are all source-declared and none is inferred: the six per-record opening triples,
the per-record numeric discriminants, the six closing tags, and seven rate constants the source
marks with its own note.

## Open questions, deliberately unassigned

None of the following is forced onto an existing key. Forcing a shape mismatch is how a wrong
authority gets established quietly, so each is carried as an unassigned slot inside the
producer/draft/computed count rather than silently filled.

DP30301 ordinal 13, the exclusively-simplified-regime taxpayer flag, is a single-character numeric
flag while the nearest producer in the closed vocabulary is a regime-composition official CODE. The
shapes do not match and the correct home is a modelling decision.

DP30301 ordinal 24, the flag for annual operations volume other than zero, has no corresponding key
in the closed 32-member producer vocabulary at all.

DP30303 ordinal 28, the no-activity declaration marker, may be a value of the filing
result-disposition producer rather than a field with its own producer. Deciding that determines
whether it is a header entry or a computed one.

The página-complementaria indicator appears three times, on DP30301, DP30304 and DP30305 at ordinal
5 of each. Whether those are three independent header fields, one producer projected three times,
or values computed from the complementaria election is a modelling decision rather than a lookup.

## Epoch delta affecting later rows

In this epoch DP30303 ordinal 29 is the complementaria declaration flag. From a later epoch the
equivalent region reads as a rectificativa self-assessment and carries additional
rectification-motive fields, one of which is itself a numbered box. That is a semantic-home MOVE,
between the amendment-evidence complementaria producer and the rectificativa producer, not a
shifted offset.

The boundary was located precisely rather than assumed, and it is NOT where it first appeared to
be. Checking the amendment region in all four epochs directly: 2023 and 2024-early both declare a
complementaria flag, while 2024-late and 2025 both declare the rectificativa self-assessment. The
move therefore happens AT 2024-late. An earlier note in this campaign described it as a 2025
boundary, which would have led the 2024-late author to inherit a complementaria assignment that
epoch does not carry, and would have wrongly warned the 2024-early author off an assignment that
epoch does carry. Both errors are avoided by locating the boundary rather than inferring it from
the two epochs that happened to be compared first.

This also accounts for part of the anchor-count jump at 2024-late, since the rectificativa block
adds fields the complementaria block did not have.

Later epoch rows must not inherit this epoch's assignment for that region. It is the exact delta
class those rows require hand review for: a delta that changes a home rather than a coordinate.

## The 2024-early epoch, assigned as a delta

The 2024-early epoch was assigned next and is near-identical in structure: 393 fixed anchors, the
same 108 declared endpoints, and ZERO unresolved anchors. Comparing every shared anchor key
between the two epochs, no anchor changes its semantic home, and no anchor present in 2023 is
absent in 2024-early.

The entire difference is four anchors, and they are a retirement rather than a move. In 2023,
DP30302 ordinals 92, 94, 120 and 122 are live simplified-regime fields carrying employee counts,
being the number of employees and the maximum number of salaried staff, for each of the two
non-agricultural activity slots. In 2024-early all four read "Reservado para la AEAT" at the same
three-character length. AEAT reserved them.

So 2024-early assigns 262 non-simplified anchors against 2023's 258, the four extra being these
new reserved runs, and its simplified residue is 131 against 2023's 135. The counts move in
lock-step and in opposite directions, as a retirement requires.

This independently corroborates the per-epoch DP30302 shares measured earlier from a different
direction: 134 for 2023 and 130 for 2024-early, differing by exactly these four fields. Two
measurements taken by different routes agree, which is worth more here than either alone.

The practical consequence is that neither epoch may inherit the other for this region. Reusing
2023 in 2024-early would declare endpoints for four fields AEAT has reserved; reusing 2024-early
in 2023 would blank four fields that are live that year. It is a second instance of the delta
class the later rows require hand review for, alongside the complementaria-to-rectificativa move.

It also refines the blocked work: the simplified endpoint deficit is not uniform across epochs, so
the declarations owed differ per epoch rather than being one set replicated five times.

## The 2024-late epoch, and a method correction that matters more than the epoch

2024-late assigns 258 non-simplified anchors with ZERO unresolved, against 413 fixed anchors and
141 simplified residue. It is the epoch where the anchor count jumps by 20, so real movement was
expected here rather than a retirement.

The first comparison was WRONG, and the way it was wrong is the reusable part. Diffing the epochs
by anchor key, meaning record identity plus ordinal, reported nine changed semantic homes,
including a record's closing constant tag apparently becoming a numbered casilla. That is not what
happened. 2024-late INSERTS fields into the middle of records, and every insertion shifts the
ordinal of everything after it, so a positional diff reports the shift as a change.

Re-diffed by field IDENTITY rather than position, the result is that ZERO anchors change their
semantic home between 2024-early and 2024-late. All nine apparent changes were insertion artifacts.

Stated for reuse: compare epochs by field identity, never by record-and-ordinal. A positional diff
conflates insertion shift with semantic change, and it fails in the direction that costs most,
manufacturing phantom changes an author would then "review" and potentially act on, while giving
no signal at all about what genuinely moved.

What genuinely changed, by identity: fifteen new fields and four removed. Six of the new ones are
numbered casillas 165 through 170 in DP30301, covering additional recargo de equivalencia and
general-regime tiers. The DP30303 complementaria pair is replaced by the rectificativa block, which
contributes the rectificativa self-assessment flag, its prior-receipt reference, a
de-registration consequence flag, two rectification-motive flags, and two numbered casillas, 108
and 111.

Two of the four apparent removals are not removals at all. The general-regime total cuota devengada,
casilla 27, and the self-assessment result, `iva.resultado`, each keep their home and their
identity; they appear as a removed-and-added pair only because the comparison key included their
formula text, and their formulas changed to enumerate the newly added tiers. That is substantive
regulatory content rather than noise: a total that gains a tier must enumerate it, and these two
totals did.

## The 2025 epoch, and the per-epoch non-simplified totals

2025 assigns with ZERO unresolved and is the smallest delta in the family. Comparing it to
2024-late by field identity: no new non-simplified identity, none removed, and no anchor changes
its semantic home. Per record, five of the six records are byte-for-byte identical in field count,
and the entire difference is DP30302 growing from 163 to 166 fields. Of those three additions one
is a reserved run and two are live simplified-regime fields, both inside the Actividad 2 block.

That corroborates the DP30302 simplified shares measured earlier by a different route once more:
140 for 2024-late against 142 for 2025, differing by exactly those two live additions. Three
independent measurements of the simplified residue now agree across the family.

The per-epoch non-simplified totals, which are the counts a map author needs, are:

| Epoch | Fixed anchors | Non-simplified assigned | Simplified residue |
| --- | --- | --- | --- |
| 2023 | 393 | 258 | 135 |
| 2024-early | 393 | 262 | 131 |
| 2024-late | 413 | 272 | 141 |
| 2025 | 416 | 273 | 143 |

Each row sums exactly, and each epoch resolved with zero unresolved anchors.

A caution about the identity-keyed comparison used here, since it has its own failure mode. An
identity key that is not unique collapses duplicates: every reserved run shares the description
"Reservado para la AEAT", so a diff keyed on identity alone reports no new entries even when the
count of reserved runs grows. The identity diff answers "did any field change its home" and
answers it well; it does NOT answer "how many anchors are there". Both questions must be asked, and
the per-record field counts are what answer the second. This is the same class of error as the
positional diff, arriving from the opposite direction.

## The 2026 epoch, and a third diff failure caught the same way

2026 assigns with ZERO unresolved: 417 fixed anchors, 274 non-simplified, 143 simplified residue.

The identity diff first reported FOUR anchors changing their semantic home, all in DP30301, with
the general-regime and recargo de equivalencia devengado fields apparently moving from casillas 165,
166, 167 and 170 to casillas 07, 08, 09 and 24. That would have been a substantial regulatory
change and it did not happen.

The cause was a collision in my own comparison key. DP30301 carries many fields whose descriptions
are identical apart from their box number: the general-regime base imponible, tipo and cuota repeat
once per rate tier, as do the recargo equivalencia triples. The key used stripped parenthetical text
and truncated at seventy characters, which cut off the trailing bracketed box number, collapsing
every tier onto one key. The mapping then retained whichever tier happened to be last, and the diff
reported the difference between two arbitrary survivors as a change.

Reading the actual fields disproves it immediately: 2026 contains boxes 150, 151, 152, 165, 166,
167, 01, 02, 03, 153, 154, 155, 04, 05, 06, 07, 08 and 09 for the general regime, and 156, 157, 158,
168, 169, 170, 16 through 24 for recargo equivalencia. The transitional tiers and the standard tiers
coexist. Nothing moved. 2026 has ZERO semantic-home changes.

The genuine 2026 delta is two fields. DP30301 gains a producer flag for entitlement to deduct the
hydrocarbon advance payment, and in DP30303 a previously reserved run becomes numbered casilla 112,
the advance payment on supplies of petrol and diesel. Net one additional anchor overall, which
matches the per-record count change of DP30301 going from 88 to 89 fields.

This is the THIRD diff method in this family to manufacture phantom changes, after the positional
key and the deduplicating identity key. Each was caught the same way, by finding the result
implausible and reading the underlying fields, and none would have been caught by a validator. The
durable rule: any comparison key for this corpus MUST retain the discriminating box number, because
descriptions alone are not unique within a record. A key that is not unique does not merely lose
information, it silently fabricates differences.

## Every epoch: assigned totals

All five epochs are now assigned, each with zero unresolved anchors.

| Epoch | Fixed anchors | Non-simplified assigned | Simplified residue |
| --- | --- | --- | --- |
| 2023 | 393 | 258 | 135 |
| 2024-early | 393 | 262 | 131 |
| 2024-late | 413 | 272 | 141 |
| 2025 | 416 | 273 | 143 |
| 2026 | 417 | 274 | 143 |

Every row sums exactly, and the five fixed-anchor totals plus thirteen prefix anchors each reproduce
the contracted 406, 406, 426, 429 and 430 per-epoch counts.

Semantic-home changes across the whole family, verified by identity with box numbers retained: the
only genuine move is the complementaria-to-rectificativa transition at 2024-late. Every other
difference between adjacent epochs is an addition, a retirement, or a formula change on a total that
gained a tier.

## Total-formula operand shifts, and an independent convergence

Three totals change their operand lists across this family, and the shifts were read directly from
the official binaries' own formula text rather than inferred:

- Casilla 27, the general-regime total cuota devengada, carries operands 152, 03, 155, 06, 09, 11,
  13, 15, 158, 18, 21, 24 and 26 in 2023 and 2024-early. From 2024-late onward it GAINS 167 and 170,
  the cuota fields of the newly added general-regime and recargo de equivalencia tiers.
- Casilla 69, the self-assessment result, gains operand 108 at the same 2024-late boundary.
- Casilla 71, the final result, is stable at 69, 70 and 109 through 2025 and gains a SUBTRACTED
  operand 112 only at 2026, reading as 69 minus 70 plus 109 minus 112. That is the petrol and diesel
  advance payment, which is the same casilla 112 this epoch introduces by converting a previously
  reserved run.

These three shifts independently corroborate row `W02.P04.S64` of the design-relayout boundary plan,
which was authored separately and which requires each revision's total-formula operand lists to be
re-derived from its own bundled design rather than copying the newest expression backwards. That row
predicts exactly these three movements at exactly these two boundaries. It reached them by reading
the registry fragments; this reading reached them by parsing AEAT's record-design binaries. Two
sources, opposite directions, same result, neither author aware of the other at the time.

The convergence matters beyond the three casillas: it means the operand shifts are a property of the
official form rather than an artefact of either method, so any tool that copies one epoch's formula
into another is wrong about live tax arithmetic and not merely untidy.

Stated generally, and this is the load-bearing sentence: epoch-to-epoch reuse of a total's formula is
unsafe precisely in the years a tier is added. This project already holds that invariant for IVA
totals — when a tier is added to any total, every downstream total and every return reconciling
against it must enumerate it — and what is visible here is AEAT applying that same invariant in its
own revisions of the form. The rule is not being asserted onto the data; the data is exhibiting it.

## One lesson with three instances: proxies are not facts

Three separate methods produced wrong answers on this surface in a single session, and they share
one root cause. Recording them together because the pattern is the finding, not any of the three
individually.

The first used description SHAPE as a proxy for payload axis: no bracket in the description was
treated as meaning not-a-projection, which misfiled thirteen live exonerado-390 fields as header
producers. The fact is whether the revision DECLARES an endpoint for that anchor.

The second used the FIRST bracket as a proxy for a field's own box number, when descriptions state
formula operands before naming the field. The fact is the TRAILING bracket, and then `number`
before `form_number`.

The third used POSITION as a proxy for identity when diffing epochs, and reported nine phantom
semantic-home changes because inserted fields shift every later ordinal. A later variant used a
TRUNCATED identity, which cut off the discriminating box number and fabricated four more. The fact
is a comparison key that retains the box number, and a separate per-record count for multiplicity.

On this surface every convenient proxy has been wrong, and the fix each time was to use the declared
fact instead. Note also how they were caught: each was found because the RESULT was implausible and
the underlying fields were then read, never because a validator objected. Every one of these would
have passed a clean bijection. That is precisely why the map rows require hand review of semantic
homes rather than mechanical validation alone.

## Render profiles: eligibility is far narrower than modelo_200 suggests

A profile may name ONLY fixed-record fields whose `aeat_type` is `Num` or `N` AND whose official
Contenido cell is BLANK, and it must then cover that eligible set EXACTLY: coverage is checked as set
equality, so a profile may neither omit an eligible field nor name an ineligible one.

Modelo 303 declares content for nearly every numeric field, whether an amount note, a `Constante`, or
a yes/no legend, so almost nothing is eligible. Per epoch the eligible sets are 3, 7, 7, 8 and 8
fields out of 317 to 340 numeric fields, and NO epoch has a single width-17 eligible field.

That is the trap for anyone reusing the modelo_200 profile's shape. Stated precisely, because the
imprecise version misleads in its own way: modelo_200's profile is dominated by width-17 COVERAGE
rather than by width-17 rules. It carries just two width-17 membership rules — one for `Num` at
fifteen integer and two decimal digits, unsigned, and one for `N` at fourteen and two with the
n-prefix-negative convention — and those two rules govern 5,550 anchors between them, alongside 126
singleton rules, for 5,676 governed anchors in total against an eligible set of exactly 5,676.

Modelo 303 needs no width-17 rule at all, and authoring one against an empty eligible set is refused
by the coverage check. Derive eligibility from this design; do not inherit another modelo's answers.

Two further facts from that profile are worth carrying, because they settle questions this epoch
raises. First, reviewed-policy evidence is well precedented rather than a fallback: 88 of modelo_200's
126 singleton rules use it, against 38 using official-source evidence, while both width-17 rules are
official-source grounded. So an all-reviewed-policy profile is consistent with established practice,
not a weaker substitute for one. Second, the semantic-kind vocabulary is exercised broadly there —
checkbox 86 times, percentage_decimal 14, enumeration 5, year_yyyy, month_mm and day_dd 4 each,
digit_string 3, date_yyyymmdd and year_last_two_digits 2 each, identifier_digits and integer once
each — and not once for a reserved run, because none was eligible. That earlier work neither met the
reserved-run case nor forced a kind onto it.

The 2023 profile is authored and validates: three singleton rules covering the Devengo ejercicio as a
four-digit year, and the two agricultural simplified-regime activity codes as two-digit identifiers.
The identifier reading is deliberate rather than convenient: an integer or decimal reading would
assert arithmetic these codes do not carry, and an enumeration reading would require canonical allowed
values which the annual Orden does not publish in this two-digit form, so an enumerated domain would
have to be invented. Coverage equality was verified against the real eligibility projection, and the
gate was proven non-vacuous by dropping a rule and confirming it reds.

All three rules carry reviewed-policy evidence rather than official-source evidence, because these
fields are eligible precisely BECAUSE their Contenido cells are blank, so there is no source text to
quote. A consequence worth knowing: `load_render_profile_source_evidence` refuses a profile carrying
no official-source evidence, since it would have no cell to read. That is coherent rather than a
defect, but it means an all-reviewed-policy profile must be supplied an evidence object with no
entries rather than one loaded from the binary.

### After the reserved-run exclusion: one piece of work, instanced five times

Once source-reserved slots are excluded from eligibility, every epoch's eligible set collapses to
the SAME three anchors, at identical sheet, row, cell and ordinal in all five designs: the Devengo
ejercicio and the two agricultural simplified-regime activity codes. The reserved runs were the
entire inter-epoch difference in the eligible sets.

So the five profiles differ ONLY in their design identity and source hash. Each carries three
singleton rules and no width-17 rule, and each was validated against its own freshly projected
eligible set with the coverage gate proven non-vacuous by dropping a rule.

Stated plainly for sizing, because the raw counts mislead in the same direction they did for the
maps: the profile half of the five map rows is not five pieces of work. It is one piece of work
instanced five times. Anyone estimating it from the 393-to-417 anchor counts, or even from the
pre-exclusion eligible counts of 3, 7, 7, 8 and 8, will overstate it.

### The reserved-run question, as it stood before the exclusion

"Reservado para la AEAT" runs are typed `Num` with a blank Contenido in this design, so they satisfy
eligibility mechanically and coverage therefore demands a rule for each. 2023 has none among its
three eligible fields, which is why its profile could be completed. Every later epoch has them: four
of seven in 2024-early and 2024-late, five of eight in 2025 and 2026, including a 110-character
reserved run typed `Num`.

The obstacle is that `semantic_kind` is a closed twelve-member vocabulary — integer, decimal,
date_yyyymmdd, enumeration, percentage_decimal, digit_string, identifier_digits, checkbox, year_yyyy,
year_last_two_digits, month_mm and day_dd — each pinned to a matching export value policy, and every
member asserts a real numeric meaning. There is no member for a source-reserved run. Declaring a
110-character reserved run an unsigned integer with a chosen digit count would invent a wire fact for
a field that carries no value, which is what this module's own docstring forbids when it says profiles
are reviewed inputs and not inference recipes.

So the question is whether reserved-but-`Num`-typed fields should be eligible at all, which would make
this an eligibility defect, or whether the vocabulary needs a member for source-reserved runs. Those
want opposite fixes. The evidence below answers it, but the decision itself is deliberately left to a
reviewer, and the rules are left unauthored.

### Evidence: the `Num` typing on reserved runs is vestigial

Modelo 200 carries 79 reserved fields and every one of them is typed `An`, with blank content. None is
eligible, because eligibility requires `Num` or `N`. So the earlier profile work never met this case,
and there is no precedent to follow — the absence is explained rather than merely observed.

Modelo 303 is more revealing still, because it is inconsistent WITHIN ITSELF. The 2023 design has nine
reserved fields and all nine are typed `An`. The 2025 design has thirteen, of which eight are `An` and
five are `Num`.

The five `Num`-typed ones are not arbitrary. Four of them sit at exactly the DP30302 positions that
carried live numeric employee-count fields in 2023 — the number of employees and the maximum number of
salaried staff for each of the two non-agricultural activity slots — which AEAT reserved from
2024-early onward. When AEAT retired those fields it rewrote the description to "Reservado para la
AEAT" and left the original `Num` type column untouched.

The `Num` typing is therefore a residue of the field's former life as a numeric quantity, not an
assertion that the reserved run carries a number. It is vestigial. That is a considerably stronger
basis than the absence of precedent: these fields are not numeric fields awaiting a wire fact, they are
retired numeric fields whose type column was never updated.

On that evidence the eligibility predicate, not the semantic-kind vocabulary, is what does not yet
account for the case. Adding a vocabulary member would be modelling a numeric meaning onto fields that
demonstrably lost theirs, and would have to be repeated for every future retirement AEAT performs the
same way.

A caution on how this was found, because it nearly went the other way: the first modelo_200 check
searched for the capitalised term and returned zero reserved fields, which would have supported a much
weaker conclusion drawn from an absence that was not real. Modelo 200 writes the term in upper case.
The count is 79, not 0, and it only appeared on a case-insensitive search. That is the fifth proxy this
surface has punished in one session, and the failure mode is identical to the others: an exact-match
convenience standing in for the fact.

## What remains for this epoch

The 135 simplified-regime anchors, once their endpoint declarations exist. The source-bound render
profile, which is not started. Only then can the map fragments be written, because the bijection
requirement means a partial map cannot be validated or landed.
