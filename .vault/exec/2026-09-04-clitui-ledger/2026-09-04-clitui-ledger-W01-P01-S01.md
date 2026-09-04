---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:ab2aef633e7b48880978d8f4d1a0f3332127702112fb7be6a45f5b593c8966e3'
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
- `verify:` `uv run ruff check dev/quality/clitui_ledger_capability_matrix.py`; `uv run basedpyright dev/quality/clitui_ledger_capability_matrix.py`; `uv run python -m compileall -q dev/quality/clitui_ledger_capability_matrix.py`; in-memory adversarial matrix probes -> `pass`

## Notes

Concurrent commit `676fd04f59` captured the initial S01 source with unrelated work, and `95302abb04` restored the corrective contract after a concurrent retire/restore pair. This scoped corrective commit records the repaired S01 source and execution metadata only.
