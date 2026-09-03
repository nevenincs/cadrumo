---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f2b65199e155125d4d5d334363969d71c39fb8151d70b95bd9d326013b6ec1e1'
step_id: 'S03'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# Retire historic-payload restoration as authority-producing behavior while retaining proposal-only diagnostics

## Scope

- `dev/registry/analysis/m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_restoration_candidates.py` -> `pass`

## Notes

- Historic restoration remains proposal-only: the renderer emits TOML to stdout and the module has no destination-path argument or filesystem-writing helper.
- Removed the unused historic-candidate compatibility alias and builder; the proposal-only API is now the sole exported surface.
- The semantic-map source reference and SHA-256 must exactly match the parsed pinned design source before historic evidence is joined.
