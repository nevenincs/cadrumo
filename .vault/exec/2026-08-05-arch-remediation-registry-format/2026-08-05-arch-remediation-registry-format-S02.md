---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0478a5c84c16c328417482cf70a89239ee2948fe5e3d96aa1ff068cf34be1573'
step_id: 'S02'
related:
  - "[[2026-08-05-arch-remediation-registry-format-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-registry-format with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-08-05-arch-remediation-registry-format-plan placeholders are machine-filled by
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
     The Propagate the corrected rule to the generated provider copies with the sync verb, confirming no generated copy carries a hand-edit and ## Scope

- `.claude/rules/modelo-export-mirrors-official-structure.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Propagate the corrected rule to the generated provider copies with the sync verb, confirming no generated copy carries a hand-edit

## Scope

- `.claude/rules/modelo-export-mirrors-official-structure.md`

## Description

- Confirm no generated provider copy carried a hand-edit before syncing.
- Propagate the corrected rule from its `.vaultspec` source with the sync verb.

## Outcome

Four generated provider copies updated from the single `.vaultspec` source; 344
other rules unchanged. The generated copies are never authored directly, so the
pre-sync check confirms the sync is a clean propagation rather than an overwrite
of someone's edit.

## Verification

The pre-sync hand-edit check compared the generated copy against its committed
form and found them equal:

    generated copy matches HEAD (no hand-edit)

The sync verb then reported its own tally:

    uv run --no-sync vaultspec-core spec rules sync
    4 updated  344 unchanged

## Notes

The hand-edit check is the load-bearing half of this step. A sync silently
overwrites a hand-edit, so running it without first confirming the generated copy
was untouched would destroy an edit and report success.
