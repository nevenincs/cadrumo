---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S268'
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
     The S268 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Complete the W06.P18 and W06.P19 evidence, refusing to close any Step whose execution record lacks a command, a non-zero collected count, an exit line, and a HEAD reference and ## Scope

- `.vault/exec/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Complete the W06.P18 and W06.P19 evidence, refusing to close any Step whose execution record lacks a command, a non-zero collected count, an exit line, and a HEAD reference

## Scope

- `.vault/exec/`

## Description

- Check every closed W06.P18 and W06.P19 Step's record against the four-element
  bar rather than asserting the bar was applied.
- Prove the checker discriminates before trusting its zero.
- Amend the records that genuinely fell short.

## Outcome

SATISFIED for the closed set, with three records amended to get there.

Measured across both phases: 37 Steps, 25 closed, 12 open. Every one of the 25
closed records carries a command, a non-zero collected count or corpus size, an
exit line, and a HEAD reference. The 12 open ones are not required to, and most
already do - they are open on their verdicts, not on their evidence.

Three of the closed records were genuinely short and were amended rather than
argued about. All three are mine: the swarm-substitute, confirmation and
unrelated-failure rows recorded a corpus and a conclusion but never quoted the
invocation that produced them. They now carry the scanner command, its result
line and its discrimination output, and the layering row carries the
`lint-imports` invocation and its `Contracts: 5 kept, 0 broken` result.

THE BAR NEEDED INTERPRETING, and getting that wrong produced four false gaps
before it produced a real one. A first pass flagged seven records as failing on
the collected-count element. Four of those were the checker's fault, not the
records': the count pattern recognised only pytest shapes, so a `lint-imports`
run reporting `Contracts: 5 kept, 0 broken`, a ruff run, a duplication run
reporting `13 clones`, and the structural scan reporting `1411 production
modules, 4250 bodies hashed` all read as countless. A discovery or recording
Step legitimately carries a corpus size where a test Step carries a collected
count, and a bar applied without that distinction manufactures failures.

The remaining two false gaps were the same mistake in the command element: my
pattern required `python -m` and the scanner is invoked as a bare `python`
script. Widening a checker until it passes is exactly the move I distrust, so
the widening was justified against the data each time rather than against the
result.

DISCRIMINATION PROVEN BEFORE THE ZERO WAS TRUSTED. A checker relaxed four times
that then reports zero failures is indistinguishable from a checker that passes
everything. Fed three synthetic records: prose with no evidence at all fails on
all four elements; a well-formed record passes all four; and - the load-bearing
case - a record quoting a real command and a real exit line but `Collected 0, 0
passed` FAILS on the count element. That last one is the whole reason the bar
names a NON-ZERO count: the default marker selects nothing for integration
modules and exits green, so a zero-collected run is unverified rather than
passing.

Gates at HEAD `99d8c77ace58d782b88a2bc72cfbd780d2a8b865`:

- Evidence-bar scan over both phases: 37 Steps parsed, 25 closed, 0 closed
  Steps failing the four-element bar.
- Discrimination probe: empty prose all-False, good record all-True, zero-count
  record False on count.

## Notes

The bar is now also enforced structurally rather than by author discipline: a
gate added under a sibling Step fails any checked Step whose execution record
carries an empty Outcome. That gate and this bar cover different halves - one
asks whether the record says anything, this asks whether what it says is
evidence - and neither subsumes the other.

Scope stated honestly: this establishes the bar for the CLOSED set at this
HEAD. It says nothing about whether those verdicts are correct, which is the
formal review's job, and it cannot speak for the 12 Steps still open.
