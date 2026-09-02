---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:89e7993dd775c42ed9b571278102fb58934e710768b69feec9dea33ba2e33b06'
step_id: 'S24'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Bind rehearsal receipts and replay drift checks to the reviewed component

## Scope

- `dev/quality/object_name_rehearsal.py`
- `dev/quality/object_name_replay.py`
- `dev/quality/tests/test_object_name_rehearsal.py`
- `dev/quality/tests/test_object_name_replay.py`

## Changes

- `M` `dev/quality/object_name_rehearsal.py`
- `M` `dev/quality/object_name_replay.py`
- `M` `dev/quality/tests/test_object_name_rehearsal.py`
- `M` `dev/quality/tests/test_object_name_replay.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_manifest.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
