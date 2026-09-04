---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9dcda566e0747096a5ebd8dba5f6dd55b8816c177f4fc8ff3ffd18c6da0f07bc'
step_id: 'S01'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Define stable capability identities, axes, gap classes, applicability, evidence coordinates, and gate predicates

## Scope

- `dev/quality/clitui_ledger_capability_matrix.py`

## Changes

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `uv run ruff check dev/quality/clitui_ledger_capability_matrix.py`; `uv run basedpyright dev/quality/clitui_ledger_capability_matrix.py`; `uv run python -m compileall -q dev/quality/clitui_ledger_capability_matrix.py`; second-pass in-memory adversarial matrix probes -> `pass`

## Notes

Concurrent commit `676fd04f59` captured the initial S01 source with unrelated work, `95302abb04` restored it after a concurrent retire/restore pair, and `b4efec8879` captured the second corrective contract with unrelated quality work. The scoped corrective commit records remaining fail-closed G0 and execution metadata only.
