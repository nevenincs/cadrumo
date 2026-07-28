---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S218'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S218 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Run the plan structural check and refuse closure while any Step remains open or malformed and ## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the plan structural check and refuse closure while any Step remains open or malformed

## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`

## Description

- Run the plan structural check and read what it refuses.

## Outcome

SATISFIED AS A CHECK, and it correctly REFUSES closure.

The structural check reports no errors. Its single warning is PLAN022,
non-monotonic Step identifiers in document order, which the check itself flags
as possibly-by-design rather than as a fault: this plan has had Steps inserted
between existing rows across several handovers, and the most recent addition -
the floor-or-prove row - was appended at the next available canonical id after
rows that sit earlier in the document. That ordering reflects writer intent.

The substantive result is the refusal. Seven Steps remain open, so closure is
correctly blocked:

- the semantic sweep, which cannot be satisfied while the code index reports
  `succeeded` at 20 sections against 3742 tracked files;
- the zero-blocker verdict, deliberately not signed while a major-class finding
  stands and three review axes were confirmed rather than re-derived;
- the docs-lane worker-death identification, whose run is in flight as this is
  written;
- the floor-or-prove row created from the review's one major finding;
- and the three closure-mechanics rows, of which this is one.

That list is the honest state of the campaign, and this row exists to make it
impossible to declare completion while it is non-empty.

Gates at HEAD `9161f3122cc9ff48e84bb6ab5a1dfb0e3084a8ae`:

- `uv run --no-sync vaultspec-core vault plan check` on the plan: no errors,
  one PLAN022 ordering warning, adjudicated as intentional.
- Plan status: 278 of 285 Steps closed, 7 open.

## Notes

The row's value is entirely in the refusal, so it is worth stating what it does
NOT establish. A structural check confirms the document is well-formed and that
open rows are open. It cannot tell whether a CLOSED row was closed honestly -
that is the evidence bar's job, and separately the outcome-populated gate's -
and it cannot tell whether the work behind a closed row was correct, which is
the review's.
