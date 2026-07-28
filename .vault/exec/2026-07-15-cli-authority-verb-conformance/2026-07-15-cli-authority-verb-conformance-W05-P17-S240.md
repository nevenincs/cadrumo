---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S240'
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
     The S240 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Remove evidence audit replay from all user documentation, generated reference expectations, examples, and terminology projections while retaining audit check and ## Scope

- `docs/`
- `dev/docs/`
- `src/cadrumo/_data/terminology/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove evidence audit replay from all user documentation, generated reference expectations, examples, and terminology projections while retaining audit check

## Scope

- `docs/`
- `dev/docs/`
- `src/cadrumo/_data/terminology/`

## Description

- Sweep every surface the row names for the retired evidence-audit replay verb.
- Separate genuine citations from unrelated live uses of the same word before
  concluding.

## Outcome

SATISFIED. The retired verb appears on none of the named surfaces.

Swept the authored documentation, the generated-reference tooling, and the
terminology projection. No occurrence of the retired evidence-bundle replay
verb survives in any of them.

The discrimination is the whole content of this row, because the word is common
and mostly legitimate here. Every surviving occurrence was classified rather
than counted:

- The terminology coverage projection carries four replay entries; all four
  name `app registry parity replay`, a DIFFERENT and live verb, together with
  its three options. Correct to keep.
- The documentation tree's other occurrences are the registry parity verb, the
  subprocess replay re-entry environment marker, revision replay inputs, a
  recipient replay guard, and generated API stubs for those modules. All live
  concepts.
- The test tree's occurrences are negative assertions that the retired verb is
  absent and its schema unregistered. That is the correct shape for a retired
  surface, not residue.

One genuine stale citation was found and fixed under the sibling row that owns
it: a modelo-390 sequence step whose prose still announced "Inspect, check,
export, and replay an evidence bundle", contradicting the blocked annotation
two lines below it that already named the real three verbs.

Gates at HEAD `1745d216608445450dedd61fdaa0a482d0ccb1e6`:

- The audit command group registers exactly `show`, `check` and `export`, read
  from the command module; an exact search for the retired verb inside it
  returns nothing.
- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed`.

## Notes

A first sweep through the shell returned matches whose matched text rendered as
a single stray character, which read as though the citations were already gone.
Re-running the same search through a second reader showed the matches intact
and negative. A search whose output is mangled is indistinguishable from one
that found nothing, so the disposition was taken from the second reader.
