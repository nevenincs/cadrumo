---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:81f1aae87fa6b95f5ccb07d975257ffed3a020fd6a8d92b4a924124b4b691e3e'
step_id: 'S21'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace minimo-descendientes-eligibility with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-04-minimo-descendientes-eligibility-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Decide whether the Art. 81.1 maternidad months are operator-asserted or engine-derived, because the engine never sees the descendants at all and takes an operator-supplied list of hijo and month pairs, so the under-three and cohabiting conditions cannot be enforced while the profile already holds the birth dates and cohabitation facts, and the answer may be a refusal, an advisory or a documented operator-asserted input but must be chosen rather than inherited, BLOCKING S15 whose window predicate has no consumer until this resolves and ## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/domain/contribuyente/family.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Decide whether the Art. 81.1 maternidad months are operator-asserted or engine-derived, because the engine never sees the descendants at all and takes an operator-supplied list of hijo and month pairs, so the under-three and cohabiting conditions cannot be enforced while the profile already holds the birth dates and cohabitation facts, and the answer may be a refusal, an advisory or a documented operator-asserted input but must be chosen rather than inherited, BLOCKING S15 whose window predicate has no consumer until this resolves

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/domain/contribuyente/family.py`

## Description

Route the Art. 81.1 child condition through the ordinary mínimo predicate, taking the
Art. 58.1 and Art. 61 norma 2ª ceilings as required caller-supplied parameters.

Add `maternidad_eligible_meses`, computing the month window from the birth date: the
birth month counts in full, the month the child turns three does not.

Cap the operator's declared employment months by that window.

Read the anualidades carve-out off the profile in the pairing, so the deducción and
the mínimo apply the same suppression.

Extract `_minimo_eligibility_profile` so the mínimo aggregate and the deducción share
one reconstruction of the family record.

Return the granted pairs, the withheld indices and the ceilings verdict from one
resolver and one evaluation.

Disclose a revision that declares the casilla but not the ceilings, rather than letting
a declared figure vanish.

## Outcome

The deducción and the mínimo now answer identically about the same descendant, which is
what the authority's own definition of the qualifying child requires. A descendant over
the Art. 58.1 rentas ceiling or excluded by the Art. 61 norma 2ª own-return rule no
longer contributes months; neither case was reachable through the age-and-cohabitation
test the connect landed against.

The month arithmetic closes a real under-grant rather than tidying one. A year-end age
test excluded a turning-three child entirely, so a mother who qualified for part of that
year received nothing for it. The window grants the pre-birthday months and the cap can
only ever reduce an over-claim, never invent an entitlement.

Verified through the real CLI in the integration lane: a child born April 2021 with
twelve declared months yields 300, and a child over the rentas ceiling yields zero with
the withholding disclosed. Both mutations bite — flattening the window drops the first
to zero, restoring the bare age test returns the second to 1.200. The domain and
application suites are green sequentially at 1777 tests.

## Notes

The suite was red at 44 tests under parallel execution and green at zero sequentially,
across Modelo 303 refund and IVA wallet modules this Step does not touch. A peer landed
two registry refactors and was rewriting several thousand Modelo 100 casilla TOMLs in the
working tree during the run. Treated as the documented loader-cache race rather than a
regression, on the project's own re-run-sequentially rule.

Four CLI integration tests fail deterministically and are not this Step's: a source
scanner rejecting the word `stub` in a peer's `test_manager_action_seam.py` from commit
`6450cda07e`; two registry-CLI tests asserting against an empty parser help; and a
Modelo 349 help test whose expected quoted string wraps across a line at the default
terminal width. That last one was checked specifically because it reads the calculate
help this campaign edited: the `--row` help block is rendered before the edited option
and neither its source default nor its locale entry appears in any commit of this
campaign, so the wrap is width-sensitive and pre-existing.

The employment months remain a single annual count per descendant, which cannot express
the month in which a post-birth Social Security registration completes its qualifying
period. That is the increment recorded separately and is not modelled here.
