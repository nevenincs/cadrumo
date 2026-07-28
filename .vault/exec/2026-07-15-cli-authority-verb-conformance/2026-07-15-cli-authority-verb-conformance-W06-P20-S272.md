---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S272'
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
     The S272 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Commit the plan file alongside execution records in every closure commit, and land the 31 closures currently held only in the working tree and ## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Commit the plan file alongside execution records in every closure commit, and land the 31 closures currently held only in the working tree

## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`

## Description

- Compare the plan's closed-Step count at HEAD against the working tree to
  establish whether any closure is still held only on disk.
- Audit every closure commit landed in this handover for whether it carries
  the plan file alongside its execution records.
- Adopt the co-commit shape as the standing practice for the remainder of the
  campaign.

## Outcome

SATISFIED on both halves.

The thirty-one working-tree-only closures are gone. The plan reads the same
closed-Step count at HEAD as in the working tree, measured directly from the
object store rather than from a status summary. Anyone reading the repository
now sees the same campaign state as any agent's tree, which was the whole
point of the Step: the closure evidence was already committed while the
closure state itself was one careless working-tree operation from being lost.

The co-commit discipline is in force for every closure landed since. Each
carries its execution record and the plan file in the same commit, verified by
listing the changed paths per commit rather than trusting the commit subjects.

One deviation is recorded rather than smoothed over. A dispatched agent split
its W05.P16 work across two commits - the gate changes in one, the records and
plan in another. That is not the letter of the Step, but it satisfies its
purpose: the requirement is that the PLAN travels with the RECORDS, so HEAD
cannot understate completion. It did. A code-then-evidence split leaves no
window in which a closure exists unrecorded.

The prior handover's twenty-seven peer closures were deliberately not swept by
the close review, and correctly so; they have since been landed by their own
authoring handovers, which is why the counts now agree.

Gates at HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`:

- `git show HEAD:<plan>` and the working-tree file both report 198 closed
  Steps.
- Path listings for the five most recent closure commits confirm the plan and
  record files travel together.

## Notes

Worth stating what this Step does NOT establish, so the next reader does not
over-read it. It proves the plan's closure state is durable and visible at
HEAD. It proves nothing about whether those closures are correct - that is the
evidence gate's job, and it is a separate Step.

The two are easy to conflate because both are satisfied by looking at the same
commits. A plan committed alongside a substantive record and a plan committed
alongside an empty scaffold are indistinguishable at this Step's level of
inspection.
