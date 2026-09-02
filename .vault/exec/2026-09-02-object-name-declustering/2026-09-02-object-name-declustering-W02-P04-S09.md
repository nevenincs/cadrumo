---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:73a2d849a43a108845a1ffb538b9d769830c178610c647d0f3cd9f35dc93538d'
step_id: 'S09'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement bounded syntax-aware rename transformations with byte-precondition and allowlist enforcement

## Scope

- `dev/quality/object_name_transform.py`

## Changes

- `A` `dev/quality/object_name_transform.py`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/object_name_transform.py` -> `pass`
