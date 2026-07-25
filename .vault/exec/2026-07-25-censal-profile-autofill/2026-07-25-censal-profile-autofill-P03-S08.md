---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S08'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censal-profile-autofill with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-25-censal-profile-autofill-plan placeholders are machine-filled by
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
     The Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement and ## Scope

- `src/cadrumo/application/live` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement

## Scope

- `src/cadrumo/application/live`

## Description

- Read the existing local-artefact censal ingestion path first and follow it as
  the template, so the live transport joins a working surface instead of opening
  a second authority.
- Add a typed reconciliation record carrying the adopted facts and the reported
  disagreements as two separate collections.
- Split a projected read against the profile record's canonical path-value
  projection: adopt where the record is blank, report where the two differ, emit
  neither where they already agree.
- Commit the split through the single cotejo apply authority, mapping each
  disagreement onto a divergence row stamped with the same provenance token.
- Export the reconciliation and commit functions from the package facade.
- Pin the behaviour with real-behaviour tests against a real encrypted profile
  record through the sanctioned write path: a blank path adopts, a matching
  declared value is neither adopted nor reported, a conflicting declared value is
  reported and left standing, the commit emits exactly one censo-applied event,
  and an operator-declared value survives a pull that disagrees with it.

## Outcome

Pulled censal facts commit through the one apply authority, and a pull cannot
overwrite what the operator declared.

Modified files:

- `src/cadrumo/application/user_profile/_censo_sync.py` — the reconciliation
  record, the blank-versus-conflict split, and the commit function.
- `src/cadrumo/application/user_profile/__init__.py` — facade exports.
- `src/cadrumo/application/user_profile/tests/test_censal_sync.py` — the
  reconciliation and commit tests.

The three-outcome split is the load-bearing part. Adopting only blank paths is
what makes the pull safe to run repeatedly; reporting rather than overwriting is
what keeps the operator the adjudicator between their own answer and the
authority's. Treating an equal value as neither adoption nor divergence keeps a
re-pull from manufacturing churn or a spurious divergence row.

Routing the commit through the existing apply authority rather than the general
field-write path is what preserves the single-event contract: one apply-commit
emits exactly one censo-applied event regardless of how many facts it carries,
and no parallel write route is opened. A test asserts the event count rather
than trusting the delegation.

## Notes

The Step row scopes this to the live application package; the work landed in the
user-profile package for the same reason as the mapping Step. The live package
holds the acquisition call only.

The provenance token this stamps was already declared and already read by the
overview calendar to decide whether censo enrolment is authority-verified, but
nothing had ever stamped it, so that branch was dormant. It is now live: a
profile carrying these facts stops raising the unverified-enrolment advisory for
censo-derived obligations. That is correct only because the consulta is an
official authority read; facts from an operator-supplied artefact or an editing
surface carry the non-official token instead and do not trigger it. This is a
visible behaviour change and was called out rather than left to be discovered.

The concurrent work enforcing the declared path and provenance sets on the fact
model landed while this Step ran. It turned the projection's path-conformance
test from a convention check into a boundary-enforced one, and its own four
failing tests and one import-boundary violation are its to reconcile; neither
touches the files changed here.
