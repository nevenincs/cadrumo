---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S160'
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
     The S160 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Refresh command-search expectations only for accepted keys and reject removed tokens and ## Scope

- `src/cadrumo/application/command_search/tests/test_command_ranking_golden.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Refresh command-search expectations only for accepted keys and reject removed tokens

## Scope

- `src/cadrumo/application/command_search/tests/test_command_ranking_golden.py`

## Description

- Run the command-ranking golden and confirm expectations cover only accepted keys.

## Outcome

The named golden passes. Its expectations resolve to accepted keys and carry no retired token, so the command-search surface ranks only live commands. A retired key surviving in the golden would have surfaced a removed door to an operator searching for a capability, which is the specific failure this row guards.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.

## Corrected 2026-07-28

The Outcome above is half right, and the wrong half matters.

Right: the golden's expectations did resolve to accepted keys and carried no
retired token. Wrong: the implication that the golden therefore guards the
search surface against retired keys. It did not. Every assertion in the module
was about ranking order, and a retired key ranks perfectly well, so a removed
door left in the descriptor set would have passed unremarked. The record
described a protection that did not exist.

The module also carried a test that could not fail: it asserted a non-empty
string literal, and its own comment conceded it was "not an assertion of
behaviour". A tautological test in a golden set is worse than no test, because
it reads as coverage.

Both are now closed. The retired hard-cutover keys are asserted absent from the
live descriptor set, as exact keys and as trailing segments so a re-registration
under a different parent is caught, with the suffix sweep matching full paths
because `config auth apoderado clear` is a retained command whose leaf token
collides with the retired `auth clear`. The tautological test is replaced by the
claim the module docstring actually makes -- that the headline results hold
without the search extra, in whichever retrieval mode is installed.

All seven retired keys are confirmed absent today against a positive control, so
this landed as a ratchet rather than a red. Verified by mutation that the
membership check discriminates.
