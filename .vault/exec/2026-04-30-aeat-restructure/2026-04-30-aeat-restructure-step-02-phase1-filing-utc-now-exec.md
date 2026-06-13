---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-describe-cert-provider-exec]]"
---

# 2026-04-30-aeat-restructure step-02 phase-1 filing.utc_now

## status

Step 2 PR 3 of 6. `__all__` removal of `aeat.application.filing.utc_now` per ADR Dead-code workstream / Phase 1.

## scope

- Remove `"utc_now"` from `src/aeat/application/filing/__init__.py` `__all__` (line 364).
- Function definition stays at `__init__.py:294`.

## pre-merge safety check

`grep -rn "from aeat\\.filing import.*utc_now\\|aeat\\.filing\\.utc_now\\|filing\\.utc_now" --include="*.py" .`: zero hits.

## verification

- `python -c "import aeat.application.filing"` — succeeds.
- `prek` pre-commit hooks — to be enforced on commit.

## next step

Step 2 PR 4 — `llm._FakeAdapter` `__all__` removal.
