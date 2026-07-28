---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S211'
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
     The S211 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Rerun every focused or full gate invalidated by a corrective edit and ## Scope

- `.vault/exec/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rerun every focused or full gate invalidated by a corrective edit

## Scope

- `.vault/exec/`

## Description

- Identify which gates a corrective edit in this campaign invalidated, and
  re-run those rather than a blanket sweep.

## Outcome

SATISFIED. Two corrective edits landed late enough to invalidate prior
evidence, and both had their gates re-run at the time.

The write-guard criterion change added nine leaves to the profile-bound
catalogue and two gates to its test module. That invalidates any earlier
reading of the guard suite and the parity suites that consume the same
catalogue. Re-run: the guard module collected 13 and exited `13 passed in
72.94s`; the write-policy mutability and risk-table parity suites collected 6
and exited `6 passed in 5.31s`. The criterion gate was additionally
mutation-proven - removing one of the nine additions reds it, naming the leaf.

The layering-dimension change altered how an aborted import-linter run is
classified and replaced the tautological test over it. Re-run: the dimension's
tests collected 2 and exited `2 passed in 2.66s`, and the live dimension
reports `all 5 of 5 import-linter contract(s) kept`. That gate was
mutation-proven too: disabling the declared-count floor flips the aborted
headline and reds the test.

The documentation edits invalidated the documented-command and sequence-contract
gates, which were re-run after EVERY page change rather than once at the end -
`362 passed` on each pass.

No blanket re-run was performed and none is claimed. The row asks for gates
invalidated by a corrective edit, not for a full sweep; the full lanes are a
separate Phase and are still in flight.

Gates at HEAD `76c94c4a81ee7a4c7f98973e87f6e8331840740b`:

- Write-guard module: collected 13, `13 passed in 72.94s`.
- Write-policy and risk-table parity: collected 6, `6 passed in 5.31s`.
- Layering dimension: collected 2, `2 passed in 2.66s`.
- Documentation conformance: collected 362, `362 passed`.

## Notes

Scope stated so the closure is not over-read: this covers gates invalidated by
THIS campaign's corrective edits. It does not speak for the full unit,
integration or documentation lanes, which are owned by their own open Steps and
have not completed.
