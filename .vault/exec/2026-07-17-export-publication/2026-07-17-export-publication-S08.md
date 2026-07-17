---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes and ## Scope

- `src/cadrumo/application/operator_surface/_risk_table.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes

## Scope

- `src/cadrumo/application/operator_surface/_risk_table.py`

## Description

- Declare `config.profile.subject_access_request` as `handoff=True` in the operator-surface risk table, matching `config.profile.export`.

## Outcome

Both purposes emit the same portable profile bundle — equally readable cleartext once it leaves the vault — so they now carry equal cleartext handoff-risk classification. The operator-surface classification-parity suite and the subject-access CLI test pass. Committed in `85f19b6e52`.

## Notes

The risk grammar exposes only the `handoff` axis for this concern; no separate cleartext field exists, so equal classification is a single equal flag.
