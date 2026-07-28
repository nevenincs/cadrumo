---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S47'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# reconcile the zero-volume prorrata branch between the two M303 revisions, where the older revision returns zero and would zero every deduction for a fully-taxable trader who declared no prorrata volumes, grounding the correction as the newer revision already does

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes`

## Description

- Re-verified the handed-over premise through the loaded registry snapshot on
  both live revisions before touching anything, rather than trusting the
  report.
- Traced what a wrong percentage actually reaches, so the defect's blast
  radius is measured rather than asserted.
- Read the applicable provisions and their full amendment history on two
  independent witnesses, to decide whether the earlier revision's law
  genuinely differs.
- Corrected the no-volume branch on the earlier revision and recorded the
  grounding, the per-revision law-invariance finding, and why zero is the
  wrong answer, at the change site.
- Added a grounding gate pinning the branch value, the agreement between the
  two revisions, parity against the independent domain authority, and a
  discrimination case that stops the gate passing on a blanket hundred.
- Proved the gate can fail by mutation and confirmed the failure lands on the
  earlier revision only.

## Outcome

The premise is real, and it was verified rather than inherited. Driving the
real registry snapshot with both prorrata volume casillas at zero, the
revision selected for filing year 2020 returns 0 and the revision selected for
filing year 2024 returns 100. The independent domain prorrata authority
returns 100 for the same input. The two computed cases used as controls agree
on both revisions: a fully taxable 1000 over 1000 returns 100 everywhere, and
a mixed 552 over 1000 returns 56 everywhere. So the divergence is isolated to
the no-volume branch and is not a symptom of a broader disagreement.

The defect is filing-grade, not cosmetic. Both prorrata volume casillas are
optional manual inputs, so a blank declaration is the ordinary state for every
trader with no exempt-without-right operations, and the computed percentage is
persisted as an observation. That observation is what the cross-period
prorrata register reads to seed the following ejercicio's provisional
percentage under the article-105 carry, and the provisional percentage is what
the ledger IVA apportionment multiplies into every common-input deducible
cuota. A zero therefore does not stay in one box: it becomes the next year's
provisional rate and scales the deducible side to nothing. The casilla-44
regularizacion advisory is the one consumer that is NOT affected, because it
returns early when the declared volumes leave no exempt-without-right
remainder, so the advisory neither fires nor is harmed on this branch either
way.

The decision was made on the law rather than on symmetry. Article 102, apartado
Uno, makes the regla de prorrata applicable only where the sujeto pasivo
performs deduction-granting operations and analogous non-granting ones
"conjuntamente". With no volumes declared that antecedent is unmet, so article
104, apartado Uno, which confines the percentage limitation to the cases where
the regla applies, never bites, and the input tax stays deductible in full
under articles 92 and 94. A percentage of zero is the article 104, apartado
Dos, answer only when the numerator is zero while the denominator is positive,
which is the computed branch and which the engine already handles correctly.
Returning zero for a blank declaration therefore asserts a total loss of the
deduction right against a taxpayer who declared no fact supporting it.

The per-revision question was answered on evidence, not assumed. The earlier
revision governs filing years 2009 to 2022. Article 102 was last amended by
Ley 3/2006, in force from 1 January 2006, which is before that window opens,
so the applicability trigger is textually identical across both revision
windows. Article 104's only later amendment is Ley 22/2013, in force from 1
January 2014, and it touches apartado Tres, item 1, leaving apartado Uno, the
fraction and the closing rounding paragraph untouched. Article 94's only
amendment inside the window is Real Decreto-ley 7/2021, effective 1 July 2021,
which rewrites apartado Uno, item 1, letter c, and does not touch the general
right-to-deduct principle. Nothing in the applicable law differs, so the
divergence was a defect in the earlier revision and not a reflection of
different law. That finding is recorded at the change site with its
amendment-history evidence, so a later reader does not have to redo it.

Three independent witnesses were read for every legal claim. The bundled
per-article extractions for articles 102 and 104 were read in full; the live
BOE consolidated text was fetched and its article blocks and amendment-note
lists were extracted for articles 94, 102, 103, 104, 105 and 106; and the
article heading map for articles 90 to 110 was read off the live text to
confirm no renumbering. The bundled and live texts agree verbatim on the
article 102, apartado Uno, trigger sentence and on the article 104 fraction.

No legal-catalogue work was needed and none was invented. The three provisions
the branch depends on all already exist in the catalogue at legal-authority
tier with bundled corpus references, BOE document ids and verbatim required
text: article 94 (operaciones cuya realizacion origina el derecho a la
deduccion), article 102 and article 104. Article 102 and article 104 are
already declared in the formula's own legal references, and article 94 is
already declared on the enclosing construct. Because no legal entry changed,
the registry-and-legal-entry atomicity constraint is satisfied trivially, and
the registry validator's three-layer coverage check is unaffected.

The change was scoped to mirror the newer revision exactly. The newer revision
grounds this branch in a comment at the change site while its legal references
carry article 104 and article 102; the earlier revision now does the same,
with the additional law-invariance paragraph. Adding article 94 to the
formula's own legal references was considered and rejected: it would have
broken the very symmetry this Step exists to establish, and it would have
diverged from the newer revision the Step's action names as the template. The
observation that neither revision declares article 94 on the formula, only on
the construct, is recorded below as a symmetric two-revision matter outside
this Step.

The gate was proven capable of failing, and of failing in the right place.
Reverting the branch literal to zero produced three failures against four
passes: both parametrisations for the earlier revision failed and the
agreement assertion failed, while both parametrisations for the newer revision
and the discrimination case still passed. That asymmetry is the evidence that
the gate detects this specific defect on this specific revision rather than
merely reacting to any change. The gate also carries its own anti-vacuity
case: a trader with a positive total volume and nothing in the numerator must
still resolve to zero, so the other assertions cannot pass on a formula that
answers a hundred for everything.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
which includes the required-text corpus check on every legal reference. The
new gate is 7 passed. The whole prorrata surface is 268 passed under parallel
workers and 268 passed again with workers disabled, so no serial test was held
out of the result. The M303 surface is 420 passed with workers disabled. The
IVA domain tree together with both prorrata grounding gates is 238 passed.
Format and lint are clean on the changed files, and the project type gate is
silent.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so it was neither
started nor probed. Grounding was done with ripgrep plus whole-file reads,
confirmed against the loaded registry snapshot rather than fragment listings,
and against the bundled corpus plus a live BOE fetch for the legal text.

Peer working state was checked before the first edit on every file this Step
touched, and all were clean. The index held no peer entries at commit time,
and the commit named its two paths explicitly.

Two observations outside this Step's scope are reported rather than fixed.

Neither M303 revision declares article 94 in the prorrata percentage formula's
own legal references, although the branch's consequence rests on it and the
enclosing construct already carries it. Declaring it would be a coherent
two-revision change, and it was deliberately not made here because this Step's
scope is the earlier revision and its stated template is the newer revision's
existing grounding shape.

The existing regression that pins the hundred default exercises only the newer
revision, because it builds its snapshot at a single filing year inside that
revision's window. That single-revision coverage is exactly what let the
earlier revision keep returning zero after the defect was closed once. The new
gate covers both revisions; whether the older regression should be widened or
retired in favour of it is a tidy-up left for the campaign's closeout.
