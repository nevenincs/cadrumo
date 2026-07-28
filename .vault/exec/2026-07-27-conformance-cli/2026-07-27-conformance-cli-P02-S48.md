---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S48'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# correct the prorrata module docstring and rounding comment which cite the autoconsumo article rather than the article that actually establishes the formula and the upward rounding, so a reader sent to it finds the rule

## Scope

- `src/cadrumo/domain/iva/_prorrata.py`

## Description

- Established the correct article independently from the bundled corpus and
  the live consolidated law, rather than taking the number from the handover.
- Read the article heading map across the whole deductions chapter, so every
  replacement citation was checked against the real heading.
- Swept every site in the module that repeated the wrong attribution, not only
  the two the Step row names.
- Corrected three sibling misattributions in the same docstrings that the same
  reading disproves.
- Quoted the mandatory-especial provision verbatim and recorded honestly where
  the implementation's threshold and the provision's wording diverge.
- Mirrored the corrected citations into the module's own test docstrings.

## Outcome

The reported miscitation is real and was confirmed on two independent
witnesses before anything was rewritten. Article 102 is headed "Regla de
prorrata". Its apartado Uno is the applicability trigger, and its apartado Dos
reads "los sujetos pasivos podran deducir integramente las cuotas soportadas
... en la medida en que se destinen a la realizacion de los autoconsumos a que
se refiere el articulo 9, numero 1, letra c" - a rule about autoconsumos that
carries nothing this module implements.

The formula and the rounding both live in article 104, headed "La prorrata
general". Apartado Dos states the fraction, multiplied by 100, with the
deduction-granting operations in the numerator as regla 1 and the whole of the
operations in the denominator as regla 2. That apartado's closing paragraph,
after regla 2, is the rounding: "La prorrata de deduccion resultante de la
aplicacion de los criterios anteriores se redondeara en la unidad superior".
Scanning the entire live consolidated law for any rounding clause returns
exactly one match, that sentence, so the attribution is not a matter of
reading preference. Article 106, apartado Uno, regla 3 independently confirms
the location by routing the common-input percentage to "el porcentaje a que se
refiere el articulo 104, apartados Dos y siguientes".

The article number was derived, never copied from the brief. The bundled
per-article extractions for articles 102 and 104 were read in full; the live
BOE consolidated text was fetched and its article blocks extracted; and the
heading map for articles 90 to 110 was read off the live text, which both
confirms the article numbers and rules out renumbering.

The sweep is wider than the two sites the Step row names, on purpose. The same
wrong attribution was repeated at seven places in the module: the module
docstring's formula bullet and its rounding bullet, the result model's class
docstring, the percentage field's description string, the private percentage
calculator's docstring, the comment directly above the rounding call, and the
public calculator's docstring. Correcting only the two named sites would have
left the identical defect one screen down, which is the exact failure the Step
exists to close, so every site carrying the attribution was corrected in one
change.

Three sibling misattributions in the same docstrings fall to the same reading
and were corrected with it. The applicability trigger was attributed to
article 101, which is headed "Regimen de deducciones en sectores diferenciados
de la actividad empresarial o profesional" and is not the trigger; the trigger
is article 102, apartado Uno. The two prorrata modalities were attributed to
articles 102 and 103, where in fact article 103, apartado Uno, declares the
two modalities and article 106 is "La prorrata especial". The per-input reglas
were attributed to article 103, apartado Uno, item 3, which does not exist -
article 103, apartado Uno, has no numbered items - where the reglas are
article 106, apartado Uno, items 1 to 3. Each replacement was checked against
the heading map and the article body.

One citation was found correct and was kept. The mandatory-especial predicate
already cited article 103, apartado Dos, which is right. Its subapartado is
now named, and the provision is quoted verbatim: the especial regime applies
"cuando el montante total de las cuotas deducibles en un ano natural por
aplicacion de la regla de prorrata general exceda en un 10 por ciento o mas
del que resultaria por aplicacion de la regla de prorrata especial", in the
wording Ley 28/2014 introduced when it lowered the margin from twenty percent.

That quotation surfaced a genuine divergence, which is documented rather than
silently corrected. The implementation applies the margin strictly, so a
general deduction landing exactly on the ten percent margin does not trip the
predicate, while the provision's "o mas" reads as reaching the margin. The two
readings differ only at exact equality. Changing it is a regulated behaviour
change on a filing-relevant rule and is outside a comment-only Step, so the
docstring now states the provision's wording, states the threshold the code
applies, and states plainly that the two differ at the boundary. A reader is
warned rather than misled, and the next agent inherits a precise target rather
than a discovery.

Nothing computes differently. Every change is a docstring, a field
description, or a comment; no expression, constant, threshold or control flow
was touched. The module was already the correct authority - it is what the
registry prorrata rounding was reconciled against in an earlier Step of this
campaign - and it remains so.

The module's own test docstrings carried the same wrong attributions and were
corrected with it, since a reader consulting the tests to understand the rule
would otherwise be sent to the same wrong articles. Two identity docstrings
cited article 102, apartado Uno, for the fraction, the rounding-contract
section header and its test cited article 102, apartado Dos, and the
per-input classification section header and its test cited article 103. Those
are now article 104, apartado Dos, and article 106, apartado Uno.

Verification run. The IVA domain tree together with both prorrata grounding
gates is 238 passed with workers disabled. The whole prorrata surface is 268
passed under parallel workers and 268 passed again with workers disabled, so
no serial test was held out of the result. The M303 surface is 420 passed with
workers disabled. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references.
The nitpicky documentation build gate is 17 passed, which is the check that
matters here because this module is autodoc'd and the module docstring now
carries a cross-reference to the mandatory-especial predicate. The core-struct
docstring link gate is 3 passed. Format and lint are clean on both changed
files, and the project type gate is silent.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so it was neither
started nor probed. Grounding was done with ripgrep plus whole-file reads and
against the bundled corpus plus a live BOE fetch for the legal text.

Peer working state was checked before the first edit on both files and both
were clean. The index held no peer entries at commit time, and the commit
named its two paths explicitly.

The generated API stub tree was not regenerated and did not need to be: no
module was added, moved or deleted by this Step, and the one new module added
by its sibling Step is a test module, which the stub tree does not cover.

One item is reported rather than fixed. The mandatory-especial threshold's
exact-equality boundary, described above, diverges from the provision's "o
mas" wording. It is a one-comparison change on a regulated predicate backed by
a core constant, so it needs its own grounded Step with an oracle rather than
a drive-by edit inside a comment-only Step.
