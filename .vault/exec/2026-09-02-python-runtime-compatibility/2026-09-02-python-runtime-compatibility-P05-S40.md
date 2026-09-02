---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:24bc46209917c46ec366d30847173bc5e1953977d7994c75f6540a0dcda9eab6'
step_id: 'S40'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Document final-runtime promotion and classifier evidence

## Scope

- `RELEASING.md`

## Changes

- `M` `RELEASING.md`
- `verify:` `uv run --no-sync python -c 'from pathlib import Path; text=Path("RELEASING.md").read_text(encoding="utf-8"); required=("dev/ci/python-runtime-matrix.json",".python-version","source-vs-binary","sealed-artifact","classifier_eligible: false","just python-compatibility","per-runtime rebuild"); missing=[item for item in required if item not in text]; assert not missing, missing; print("release-runtime-promotion docs: pass")'` -> `pass`
