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
