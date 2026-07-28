---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S163'
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
     The S163 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Rewrite authentication procedures for login, logout, reset, and backend-free certificate secrets and ## Scope

- `docs/how-to/authenticate-with-aeat.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite authentication procedures for login, logout, reset, and backend-free certificate secrets

## Scope

- `docs/how-to/authenticate-with-aeat.md`

## Description

- Read the accepted authentication and certificate grammar from the live CLI.
- Check the page's four named topics against that surface.

## Outcome

SATISFIED by verification; no rewrite was needed.

All four topics are present and correct: login, logout and reset are taught
with the accepted verbs, and certificate custody is taught as
`config auth certificate secret set --name`, matching the live signature where
`--name` is required.

The load-bearing check is the NEGATIVE one, and it passes: the word "backend"
appears zero times on the page. The row asks for backend-FREE certificate
secrets, so zero is the target state rather than a gap - the retired backend
selector, keyring spellings and migration surface are absent from the
operator-facing text exactly as the cutover intended.

The page teaches the family under `config auth certificate`, which is where the
live tree puts it. An earlier assumption in this handover that the verb lived
at `config certificate` was wrong; there is no such leaf.

Gates at HEAD `ec62e04591f495a4553abd9da23b0a28766938c8`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.89s`. The
  conformance suite resolves every command these pages cite against the live
  Click tree, so a spelling error here is a hard failure rather than a silent
  dead instruction.

## Notes

Nothing to fix, and the record exists to make that checkable. A row closed with
"already correct" and no evidence is indistinguishable from one closed without
looking.
