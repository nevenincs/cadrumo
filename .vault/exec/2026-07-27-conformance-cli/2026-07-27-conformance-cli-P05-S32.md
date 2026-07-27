---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S32'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S32 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The amend the ADR boundary wording to name every wheel-shipped module under src/cadrumo and rule the two open questions on single-versus-dual boundary-detector authority and on whether the filing-year grounding resolver belongs on the public registry facade and ## Scope

- `.vault/adr` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# amend the ADR boundary wording to name every wheel-shipped module under src/cadrumo and rule the two open questions on single-versus-dual boundary-detector authority and on whether the filing-year grounding resolver belongs on the public registry facade

## Scope

- `.vault/adr`

## Description

- Amend the accepted ADR in place, per the amend-not-supersede discipline: this
  is concretization of an accepted decision, not a pivot, so the record is
  rewritten and its status stays `accepted`.
- Correct the boundary wording from the whole `src/cadrumo` tree to every
  wheel-shipped module under it, and state the exclusion explicitly: a
  wheel-excluded test tree may reach into `dev/`, because that reach cannot
  follow the package to an installed user.
- Rule boundary-detector ownership as single-authority, with the rejected
  alternative and the reason recorded.
- Rule degraded-mode labelling as row-level rather than container-level.
- Rule the filing-year grounding resolver off the public registry facade.

## Outcome

Three questions escalated by the two review rounds are settled in the one record
that governs them, closing the gap where the ADR text and the landed code stated
different rules.

Boundary-detector ownership went to a single authority. Two independently
authored detectors were the alternative and were rejected on evidence rather
than taste: the duplication had already diverged inside a single campaign, with
the shipped-`conftest.py` case present in one copy and absent from the other. A
silently forked authority is worse than either coherent option. The objection
that the boundary test must be self-contained to prove the boundary does not
survive scrutiny, because the test module is wheel-excluded and the scan's own
imports have no bearing on the shipped surface it measures.

Degraded-mode labelling is row-level. A container-level flag is lost the moment
a renderer serialises rows or a composer merges them with rows from a validated
source, at which point a degraded row is indistinguishable from an authoritative
one. The conformance profile composer already implements it this way, so the
ruling aligns the classification fold with the shipped precedent rather than
inventing a third convention.

The filing-year grounding resolver stays off the public facade. It is
period-agnostic and total where the law-determined resolver takes a filing-year
and period pair and raises on an ambiguous or absent match. Sitting in one
namespace under an inviting name, it is one autocomplete away from a calculation
path silently dropping the period axis and abstaining where the law requires a
refusal.

## Notes

Adjudicated by the coordinator rather than delegated, because each question is a
decision an executor must not settle alone and two of them had already been
deferred once by executors who correctly declined to rule.

The boundary-wording correction is the one item here that changes what a gate
should enforce rather than only what the record says. The landed gate already
scopes to shipped modules, so the code was right and the record was wrong; this
amendment moves the record to the code rather than the reverse.

No verification gate applies to a decision record. The vault check and the plan
verbs are the only mechanical confirmation, and the substantive check is that
each ruling names its rejected alternative and the evidence for the choice.
