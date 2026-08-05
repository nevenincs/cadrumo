---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5bdae8eb0e2e88b6e78c34e2806ba9d3289c59adf41770d6d861943b9371b3af'
step_id: 'S14'
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
     The S14 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Fix the embedded newline in the rd-439-2007 art-76 legal entry notes field, the validator rejects any Unicode C category and a narrower scan for control characters reads as clean and ## Scope

- `src/cadrumo/_data/registry/aeat/legal` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Fix the embedded newline in the rd-439-2007 art-76 legal entry notes field, the validator rejects any Unicode C category and a narrower scan for control characters reads as clean

## Scope

- `src/cadrumo/_data/registry/aeat/legal`

## Description

- Restore the line continuations whose absence embedded newlines in legal-entry notes fields.

## Outcome

Landed as `0eb0ef20f0` ("fix(legal): restore the line continuations four notes fields were
missing"), three files, 6 insertions and 6 deletions.

## Verification

    git log --format=%H --grep="restore the line continuations" -1
    git show 0eb0ef20f0 --numstat
    3       3       src/cadrumo/_data/registry/aeat/legal/irpf.toml
    2       2       src/cadrumo/_data/registry/aeat/legal/iva-flow.toml
    1       1       (third legal catalogue)

## Notes

**The landed work is wider than the row, which is the opposite of the failure the closure rule
guards against but is still worth recording.** The row names one entry, the rd-439-2007 art-76
notes field. The commit repairs four notes fields across three catalogues, so the row's entry
is a member of the set fixed rather than the whole of it.

Recorded because a later reader auditing "was art-76 fixed" gets a yes, while one auditing
"what did this row change" would otherwise meet three further edits with no explanation. The
row closes on its own claim being satisfied, not on the row and the commit being coextensive.
