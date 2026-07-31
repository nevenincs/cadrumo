---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:5e171874b2672ad80e24f951243a770a726fe8cd9c0908e0c4acee024b8f3bbd'
step_id: 'S31'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# correct the prorrata percentage rounding from the shared integer code, which rounds half-up, to a rounding that always rounds upward as LIVA article 104.Dos.2 requires, adding the new rounding code rather than changing the shared vocabulary

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Description

- Verified the rounding direction against the bundled consolidated law, then
  against the live BOE consolidated text, before touching anything.
- Reproduced the defect through the real registry engine on BOTH live M303
  revisions and recorded the before figures.
- Added a new closed-vocabulary rounding code that always takes the result to
  the next unit up, leaving the shared half-up code untouched for its other
  consumer.
- Taught BOTH interpreters of the rounding vocabulary the new code: the
  calculate-path runtime and the workbook renderer.
- Re-pointed the prorrata percentage formula on both live revisions and recorded
  the binding provision at each change site.
- Added a grounding gate that pins the direction, pins that the shared code is
  unchanged, proves its own ratio set discriminates, and compares the registry
  against the independent domain authority.

## Outcome

The defect is real, was live on both M303 revisions, and is closed.

The provision is LIVA article 104, apartado Dos. Its closing paragraph reads
"La prorrata de deduccion resultante de la aplicacion de los criterios
anteriores se redondeara en la unidad superior". It is the ONLY clause matching
`redonde` in the whole of Ley 37/1992, so the direction is not a matter of
interpretation. Three independent witnesses were read: the bundled per-article
extraction, the bundled full consolidated law, and the live BOE consolidated
text fetched at the `#a104` block anchor, which agree verbatim. The article
heading is "Articulo 104. La prorrata general." in both the bundle and live BOE,
so the article number has not been renumbered.

The Step row and the originating audit both cited article 104.Dos.2. The
apartado's numbered items 1 and 2 are the numerator and the denominator; the
rounding sentence is the CLOSING paragraph of apartado Dos, after item 2. The
grounding recorded in code therefore names article 104.Dos rather than
104.Dos.2. Article 102.Dos, which the domain module cites for the same rule, is
about autoconsumos and does not carry it; that miscitation is reported below and
was not corrected here.

Both live revisions were affected, not one. The formula
`modelo-303-iva-prorrata-porcentaje` is declared identically in the
2009-y-siguientes and the 2023-y-siguientes fragments, and both carried the
shared half-up code. The rounding sentence has stood unamended since the
original 1992 publication, so it binds both, and correcting only the current
revision would have left the defect live for every amended filing of a year
before 2023.

Measured before and after, through the real registry engine, per revision. The
2009-y-siguientes revision at filing year 2020 and the 2023-y-siguientes
revision at filing year 2024 produced identical figures at each step. A ratio of
55,2 % returned 55 before and returns 56 after; 60,1 % returned 60 and returns
61; 70,4 % returned 70 and returns 71. The two AEAT manual figures did NOT move:
the manual's provisional 72,72 % stays 73 and its definitive 55,55 % stays 56,
both before and after, which is the check that the correction is a correction
and not a fixture-breaking guess. An exact 50,0 % stays 50 after the change,
because taking a result to the unidad superior raises a fractional result and
does not add a unit to an exact one.

The shared vocabulary was extended, never redefined. A new rounding-code member
was added for the always-up direction; the existing half-up member is unchanged
and now carries its own regression pin. The registry declares 1307 rounding
values today: 1304 half-up money-to-cents, and three whole-unit values, of which
the two corrected here were the prorrata percentage on each revision. The one
remaining half-up whole-unit consumer is the Modelo 123 perceptor-count total,
where the operands are already integers and no provision directs a rounding
side, so half-up is correct there and it was deliberately left alone. Six
further occurrences of a `rounding` key in the registry belong to a DIFFERENT
axis, the verification-expectation tolerance field, and are outside this
vocabulary.

The rounding vocabulary has eight consumers and TWO interpreters, and both
interpreters had to be taught the new code. The declaration site is the closed
enum plus its hydration validator; the schema field on the formula definition
and its re-export carry it; the package facade exports it. The first interpreter
is the calculate-path rounding applier, reached from its single call site in the
formula runtime. The second interpreter is the workbook renderer, which maps the
code to a live spreadsheet function and stamps the rule name onto two record
models. The eighth consumer is the revision-diff comparison, which compares
codes for equality and is code-agnostic. Handling the new code in only the first
interpreter would have made the workbook render a nearest-unit rounding while
the calculate path rounds up, which is exactly the pull-versus-calculate
divergence the one-aggregation-path rule exists to prevent; the renderer now
emits the ceiling function. Its error path already refuses an unhandled code
loudly, so a future code that skips it fails rather than silently rendering the
wrong rounding.

The direction ambiguity was resolved rather than assumed. Rounding toward
positive infinity and rounding away from zero differ for a negative operand. The
target casilla declares a non-negative sign with a zero minimum and a hundred
maximum in the registry, so the two readings coincide for every value this code
can currently see; the runtime docstring records the precondition and states
that a future negative-capable target must declare which reading its provision
means before enrolling.

No legal-catalogue work was needed and none was invented. The catalogue entry
for the article already exists at legal-authority tier with a corpus reference
into the bundled per-article file at its own anchor, the BOE document id, the
permalink, and a required-text list whose FIRST entry is the rounding sentence
verbatim. Its notes already state that the percentage is rounded up to the
unidad superior. Its review provenance is honest agent authorship pending
operator re-stamp and was not touched. The formula already declared the article
in its legal references. Because no legal entry changed, the atomicity
constraint between registry files and legal entries is satisfied trivially.

The new gate was proven capable of failing, twice, by mutation. Reverting the
2023 revision declaration to the shared code produced six failures against
sixteen passes, all on that revision. Mutating the runtime's new branch back to
half-up produced twelve failures against ten passes, symmetrically across both
revisions. The gate also caught its own vacuity while being written: a candidate
volume pair at exactly 76,5 % was rejected by the discrimination test because
half-up already rounds a half upward, so that pair could not have detected a
regression; it was replaced with 76,4 %.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
which includes the required-text corpus check on every legal reference. The new
gate is 22 passed. The calc-sheets, offline-versus-online conformance, registry
and IVA domain suites together are 3394 passed. The whole prorrata surface is
231 passed under parallel workers and 231 passed again with workers disabled, so
no serial test was held out of the result. Format and lint are clean on all five
changed source files. The project type gate reports 18 diagnostics, none in any
file this Step touched. The API stub tree is conformant with no drift.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so grounding was done
with ripgrep plus whole-file reads, confirmed against the loaded registry
snapshot rather than fragment listings, and against the bundled corpus plus a
live BOE fetch for the legal text.

This record replaces an earlier one written against a different Step action. The
row originally asked for casilla 44 to be modelled as a computed casilla; that
action was refused on evidence and the row was subsequently rewritten to the
rounding correction, which the earlier executor discovered while grounding the
refusal. The scaffold was regenerated so the heading matches the current row.

Two defects were observed outside this Step's scope and are reported rather than
fixed.

The domain prorrata module attributes the rounding rule, and the general
prorrata formula itself, to article 102.Uno and 102.Dos in its module docstring
and in the comment directly above the rounding call. Article 102 is "Regla de
prorrata" and its apartado Dos is about autoconsumos; the formula and the
rounding both live in article 104.Dos. The module's arithmetic is correct and
was the authority this Step reconciled the registry against, so nothing computes
wrongly, but a reader sent to article 102 will not find the rule. The correction
is a comment-only change in a module this Step did not otherwise touch and
belongs in its own change.

The two live M303 revisions disagree on the no-prorrata-data branch. When the
total volume is zero the 2023 revision returns 100, with a comment grounding
that in the full right to deduct and naming the defect it closed; the 2009
revision still returns 0, which would zero every deduction for a fully taxable
trader who simply declared no prorrata volumes. That is the same class of defect
the newer revision already fixed, still live for amended filings of years before
2023. It needs its own grounded Step and was not touched here.
