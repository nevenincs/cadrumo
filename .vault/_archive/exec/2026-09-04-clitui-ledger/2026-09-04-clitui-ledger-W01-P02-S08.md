---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:a6cce89dc1f89f93fe2f4eaa7b272601df8288933e84b5610a88260c2e376f34'
step_id: 'S08'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Adjudicate canonical semantic homes and typed command-result contracts for every denominator row

## Scope

- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

## Changes

- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S08.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` exact selection accounting -> `760 observations / 769 selected edges / 4 one-to-many observations / 9 split edges / 59 multi-observation rows / 76 duplicate selections / 693 rows`
- `verify:` union schema/digest -> `2` / `sha256:8119bedd03babf7b1400bf310cd9e847b1f7f472a671b6ccb482cc583ad9a3bb`

## Notes

Shared worktree automation committed the union implementation and detector changes across `9c3d32a2f4`, `421eafcbd7`, `96604c8ee8`, `ede8ec4d29`, `df3e6a56f8`, and `bafb4d0e0a`, then captured the reference and Step Record in `6355355b90` and `d9feb980ac` while S08 remained active. The split is retained rather than rewriting concurrent history.

The first independent S08 review reopened the step with four HIGH findings. The remediation removes prefix/token/default semantic inference for non-registry rows, requires exact equality between the 147 live non-registry identities and their authored decisions, corrects persistent LLM/provenance/diagnostic/download effects, validates the four remaining existing homes against live callable signatures, and records explicit rule, counterparty, export, split, and classify/LLM joins. G0 remains OPEN; S09-S14 remain required.

The remediation review reopened S08 with two remaining HIGH findings. The second remediation commits the exact ordered selections for all 214 non-registry observation identities, rejects identity reuse and added/removed/duplicate/changed observations, validates the 546 mechanically projected registry observations, and makes provenance applicable with coherent gap and lineage-proof requirements for five provenance queries plus evidence download.

The serialized-authority review reopened S08 once more. The third remediation upgrades the envelope to schema v2, embeds the validated registry and TUI projections, binds canonical `(source, observation_id)` selections for all 760 observations, rederives registry observations from the registry census owner, and recomputes source counts, source digests, row memberships/sources, accounting, and aggregate digest during deserialization.
