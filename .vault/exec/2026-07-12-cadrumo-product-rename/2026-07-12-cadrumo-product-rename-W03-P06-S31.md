---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S31'
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
     The S31 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Move the official companion project directory and ## Scope

- `packaging/aeat_data_official to packaging/cadrumo_data_official` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the official companion project directory

## Scope

- `packaging/aeat_data_official to packaging/cadrumo_data_official`

## Description

- Inspect live status and history for the former and canonical official companion directories.
- Resolve both absolute paths and verify they remain inside the shared workspace before any filesystem action.
- Compare the historical and current logical file sets and classify content deltas separately to S32/S33.
- Verify the root source mapping selects the canonical target and remove one ignored compiled cache with literal non-recursive operations.

## Outcome

Commit `f99ee0c821` overtook the directory move. The former directory is absent, the canonical target exists, and all three historical logical files (`README.md`, `hatch_build.py`, and `pyproject.toml`) exist under the target with no missing, extra, or colliding logical path. Git identifies the build hook and metadata as renames; the README was recreated at the target while its content was updated as part of the combined S32/S33 edits.

The root `cadrumo-data-official` source mapping resolves exactly to the target directory. One ignored `hatch_build.cpython-313.pyc` and its empty cache directory were removed after workspace containment checks; no tracked file changed.

## Notes

S31 is evidence-only because the move was already complete. S32 and S33 metadata and hatch content remain untouched by this Step.

Formal review found no issue and independently confirmed the one-to-one mapping, zero collisions, clean target status, and safe ignored-cache cleanup.
