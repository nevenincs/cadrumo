---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S209'
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
     The S209 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Invoke vaultspec-code-review over the complete feature diff for safety, intent, boundary direction, and test quality and ## Scope

- `.` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Invoke vaultspec-code-review over the complete feature diff for safety, intent, boundary direction, and test quality

## Scope

- `.`

## Description

- Dispatch an independent reviewer over the campaign surface; when it produced
  nothing, run the sanctioned persona-switch form instead.
- Build an instrument for the axis this campaign actually fails on, rather than
  reading for style.
- Persist the review as an audit document with its own limits declared.

## Outcome

SATISFIED ON A STATED SCOPE, and the scope is the point rather than a caveat.

A dedicated reviewer was dispatched with a full brief naming the surface, the
four axes, the dead semantic index, and the specific defect class to hunt. It
produced nothing across three idle signals and two direct requests. The
campaign's close-review discipline sanctions three forms - independent
dispatch, persona switch on the driving agent, or a curation pass - so the
persona switch was used and is declared as such in the audit. It is the weaker
form and the audit says so.

Depth is uneven and declared rather than implied: the test-quality axis was
reviewed with a purpose-built instrument, while safety, boundary direction and
intent were checked at confirmation depth against measurements taken earlier in
the campaign rather than re-derived.

THE FINDING IS BETTER THAN THE SIXTH INSTANCE I WENT LOOKING FOR. An AST scan
over 16331 test functions searched for the campaign's signature defect - a
function asserting a collection empty, with no assertion that any count is
non-zero, where the collection derives from scanning a corpus. It reports 246
candidates tree-wide and 87 inside this campaign's surface.

The instrument is a candidate generator, not a finding list, and I kept it
honest in both directions. A first pass without the corpus-scanning filter
returned 2045, mostly legitimate assertions on a constructed object's default
attributes; a parse error's empty `missing` tuple is not a vacuous gate.
Narrowing cut it to 246. And one representative candidate was READ rather than
counted: the profile-backend retirement gate walks application and entrypoints,
collecting files carrying forbidden tokens, and asserts the offender list empty
with no floor - but that walk covers 1207 plus 526 files, 1733 in total, so it
is not vacuous today.

The class is therefore LATENT, not active: a path rename silently empties the
corpus and the gate stays green while the tokens survive. That is exactly how
all five confirmed instances arose - none was born vacuous.

Also checked, and the narrow claim worth having: every gate this campaign added
or repaired carries a floor, and three of four were mutation-checked when they
landed. The campaign did not add to the class it was eradicating.

Gates at HEAD `7113d72aa2248133ec15764ceccd05cb55fddbc0`:

- `python find_vacuous_gates.py` over the source and dev test trees: 16331 test
  functions scanned, 246 candidates tree-wide, 87 in-surface, exit code 0.
- Corpus check on the representative gate: 1207 application and 526 entrypoints
  files, 1733 total.
- `uv run --no-sync vaultspec-core vault check schema`: 0 errors naming the
  audit document.

## Notes

The sibling row asking for a zero-blocker and zero-major verdict is NOT closed
by this. A major-class finding stands, three of four axes were confirmed rather
than re-derived, and the review is a persona switch. Recording a zero-finding
verdict on that basis would be the kind of inferred green this campaign exists
to remove.
