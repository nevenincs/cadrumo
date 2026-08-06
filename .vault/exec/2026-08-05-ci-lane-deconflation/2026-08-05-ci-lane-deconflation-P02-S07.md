---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:ff9dbb9a8227b9c5f1bc567349c59c073f72d1f4b1ad9841dd2f38b30415804f'
step_id: 'S07'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Reshape overview.calendar profiles to a per-profile summary with detail behind a per-profile call, the resource_link this row first prescribed is refused because resolution re-runs a read verb over persisted state while this verb is computed from a clock and ## Scope

- `src/cadrumo/entrypoints/mcp` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reshape overview.calendar profiles to a per-profile summary with detail behind a per-profile call, the resource_link this row first prescribed is refused because resolution re-runs a read verb over persisted state while this verb is computed from a clock

## Scope

- `src/cadrumo/entrypoints/mcp`

## Description

- Replace the embedded per-profile calendar with a summary carrying counts and the next obligation due.
- Verify against the allowance the governing ADR set, not against the headline budget.

## Outcome

Landed in commit `1b3d18bd26`, 14 insertions and 6 deletions to
`src/cadrumo/entrypoints/cli/_overview_payloads.py`. The profile payload's
`calendar: OverviewCalendarPayload` field is gone, replaced by counts and
`next_due_modelo` / `next_due_period` / `next_due_closes_on`, with the docstring stating that
the next-due value is the earliest obligation closing at or after the queried date.

**Measured at HEAD:**

    total     15896   (was 20589, budget 18000)
    $defs     11533 across 11 definitions   (was 15844 across 13)
    titles        0

**The criterion this row closes against is the second number, not the first.** The governing
ADR argued the payload was over its REAL allowance — roughly 13300 once the ~4700 shared
envelope spine is subtracted — while its definitions alone were 15844. Definitions are now
11533, roughly 1800 under. A reshape designed against the nominal 18000 would have passed the
gate and remained over the allowance; this one cleared both.

## Verification

    git show 1b3d18bd26 --numstat -- src/cadrumo/entrypoints/cli/_overview_payloads.py
    14      6       src/cadrumo/entrypoints/cli/_overview_payloads.py

The schema decomposition above was measured directly from `build_tool_descriptors()` rather
than inferred from the diff.

**The commit is not resolvable by subject.** It carries the message "User docs buildout work
in progress" — a bulk snapshot that swept this change in with unrelated work. So the
convention of resolving a sha with `git log --grep=<subject>` does not work for this row, and
the sha is cited directly. Recorded because a later reader following the campaign's own
verification convention will find nothing and should not conclude the work is absent.

**One limit on this record's evidence.** The measurement was taken in a working tree carrying
uncommitted production modules, so it is a statement about the tree rather than about HEAD.
For this row that distinction is narrow — the payload module itself is committed and the
measured schema is built from committed definitions — but it is the same class of claim this
campaign's honesty review found unsafe elsewhere, and it would be inconsistent to record it
without the qualifier.

## Notes

**This row was refused earlier by me, and the refusal was correct when made.** At that time
the reshape had not landed: the schema measured 20589, unchanged, with no commit touching the
payload modules. What had landed was the ADR ruling on the reshape, not the reshape.

The refusal went stale when the implementation landed and I did not revisit it. It was
surfaced by the campaign-close honesty review as a finding against myself — a judgement that
was right at the time and left standing after its premise changed, which is the failure mode
that review exists to catch.

**The row's text was reworded before closure and this record closes against the reworded
text.** It originally prescribed moving the bulk payload to a `resource_link`; the governing
ADR refuses that remedy, because resolution re-runs a read verb over persisted state while
this verb is computed from a clock, so a link would return rows the call never summarised.
Closing against the original text would have certified the wrong work as done.
