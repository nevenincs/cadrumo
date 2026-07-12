---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S28'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Move the manuals companion project directory and ## Scope

- `packaging/aeat_data_manuals to packaging/cadrumo_data_manuals` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the manuals companion project directory

## Scope

- `packaging/aeat_data_manuals to packaging/cadrumo_data_manuals`

## Description

- Verify the resolved former and current companion paths remain inside the workspace.
- Reconcile the already-committed directory move in `f99ee0c821` instead of moving onto an existing target.
- Compare the three pre-move logical filenames with the three target filenames.
- Confirm the former directory is absent and the root source mapping resolves to the current directory.

## Outcome

The manuals companion directory-move outcome is complete. `README.md`,
`hatch_build.py`, and `pyproject.toml` map one-for-one from the former directory
to the current directory; the former path is absent, the current path exists,
and the root project source mapping names it. There were no filename collisions.

## Notes

Commit `f99ee0c821` overtook S28 by combining the directory move with the S29
metadata and S30 build-mapping edits. Consequently, the three target blob hashes
differ from their pre-move blobs; those differences belong to the later content
steps and were not reverted. One ignored compiled bytecode file was removed by
verified literal path before validation. No tracked or untracked companion source
content was deleted, and S29/S30 remain open for independent reconciliation.
