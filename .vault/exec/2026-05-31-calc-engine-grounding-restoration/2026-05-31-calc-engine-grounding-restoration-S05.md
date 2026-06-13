---
tags:
  - "#exec"
  - "#calc-engine-grounding-swarm"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S05
related:
  - '[[2026-05-21-calculation-grounding-swarm-r2-audit]]'
---

# calc-engine-grounding-restoration S05 — HIGH-2: Google Sheets calc CLI missing legal_refs/source_refs

## Finding

Audit: `2026-05-21-calculation-grounding-swarm-r2-audit` F1 / task #566 HIGH-2.

`_compute_casillas_from_pull` in `_config/_google.py` returned per-entry dicts
with only `casilla_id`, `value`, and `formula_id`. The `legal_refs` and
`source_refs` fields available on `RegistryCalculationEntry` were silently dropped.

## Surface

`src/aeat/entrypoints/cli/_config/_google.py` — `_compute_casillas_from_pull`.

## Fix

Extended per-entry dict to include `"legal_refs": list(entry.legal_refs)` and
`"source_refs": list(entry.source_refs)`. Added docstring clarifying that the
payload preserves regulatory grounding per the `aeat-calculation-grounding` rule.

## Status

Closed (fix pre-existing in HEAD; confirmed by grep and `git show HEAD`).
No new commit required for this session — the fix was landed in a prior
session on this branch.
