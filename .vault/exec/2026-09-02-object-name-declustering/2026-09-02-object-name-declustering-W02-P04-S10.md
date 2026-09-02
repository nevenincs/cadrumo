---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4bdd7f6f3a9eefa729849f6e4a890cc46578fa053a9082f363077590c8a101ed'
step_id: 'S10'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Test exact edits, unsupported constructs, changed-path bounds, and byte-level refusal behavior

## Scope

- `dev/quality/tests/test_object_name_transform.py`

## Changes

- `A` `dev/quality/tests/test_object_name_transform.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_transform.py dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_transform.py dev/quality/object_name_transform.py` -> `pass`
