---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S28'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

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
