---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:89307152c4c48c23c76a8ad032ee366bdc454509c15b14eabfd16f8099a1b71d'
step_id: 'S228'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S228 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Replace the inline profile-delete command and false active-delete claim with a terminal real-execution sequence that logs out and deletes only its sandbox profile and ## Scope

- `docs/how-to/profile-setup.md and docs/_sequences/contracts/how-to/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the inline profile-delete command and false active-delete claim with a terminal real-execution sequence that logs out and deletes only its sandbox profile

## Scope

- `docs/how-to/profile-setup.md and docs/_sequences/contracts/how-to/`

## Description

- Replace the static blocked delete example with a visible logout followed by
  the terminal exact-name delete command and a `deleted == true` assertion.
- Correct the guide's false active-delete wording to require logout before the
  exact irreversible deletion.
- Run the real page refresh after the concurrent Modelo 303 and 322 authority
  repairs landed.
- Compare the subprocess refusal with the CLI admission registry and lifecycle
  tests, and record the unresolved boundary contradiction for follow-on work.

## Outcome

S228 remains open. The real runner proves logout succeeds but deletion then
fails at the root login gate with exit 2, so no CLI-owned golden can be
generated and the documented journey is not yet executable product truth.

S238 resolved that boundary contradiction: logged-out inactive deletion now
reaches the custody transaction while active deletion still refuses. The real
sequence refresh produced its CLI-owned golden with an inactive post-state and
`deleted == true`. S239 masks only the freshly encrypted destroyed-byte digest.
Moving deletion after history makes it the guide's terminal profile operation.
Independent formal re-review passed with no findings, so S228 is closed.

## Notes

- Concurrent commits `d6d45d618c` and `32567777ce` captured the scaffold and
  target documentation changes while this execution was in progress; they are
  provenance, not successful closure.
- Before the registry repairs, refresh, page check, and nitpicky docs setup were
  blocked by missing Modelo 303/322 deadline-window authority. Commits
  `29f9785808` and `c2f4334a5e` removed that external initialization blocker.
- Focused profile-delete integration tests passed 5 tests and documented-command
  conformance passed 349 tests, but those in-process results do not override the
  real subprocess refusal observed by the sequence runner.
- Formal review requires the missing generated golden and therefore remains
  changes-required.
- Focused page golden checking and documented-command conformance were observed
  green after S238/S239 (349 conformance cases). A later closure rerun was
  blocked before profile execution by concurrent registry catalogue WIP, while
  broader sequence and nitpicky gates also reported unrelated multi-page
  golden/baseline drift. These external failures do not weaken the exact S228
  golden, post-state, or formal review evidence.
