---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5d6c0734678d5792b762dcfe3b988670663b5bb3f8941c363c0d7402e947c5d6'
step_id: 'S23'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Bind manifest staleness to selected identities and declared bytes

## Scope

- `dev/quality/object_name_manifest.py`
- `dev/quality/tests/test_object_name_manifest.py`

## Changes

- `M` `dev/quality/object_name_manifest.py`
- `M` `dev/quality/tests/test_object_name_manifest.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_manifest.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_manifest.py dev/quality/tests/test_object_name_manifest.py` -> `pass`
