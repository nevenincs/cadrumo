---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2de22aa2f542a452299658cf8fd3db4d34a5e166a1f6ff41b03d35779576a230'
step_id: 'S38'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Document local runtime selection and source versus binary evidence

## Scope

- `CONTRIBUTING.md`

## Changes

- `M` `CONTRIBUTING.md`
- `verify:` `uv run --no-sync python -c 'from pathlib import Path; links=("docs/workstation-setup.md","dev/ci/python-runtime-matrix.json","RELEASING.md","REGISTRY-CONFORMANCE.md",".python-version"); assert all(Path(link).is_file() for link in links); print("root-doc local links: pass")'` -> `pass`
