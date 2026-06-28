---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-llm-all-cleanup-exec]]"
---

# 2026-04-30-aeat-restructure step-02 phase-1 schema._extractor.py deletion

## status

Step 2 PR 5 of 5 — final Phase-1 dead-code item. Whole-file deletion of `src/aeat/domain/schema/_extractor.py` per research-doc Decision 7 (`Extractor` Protocol fate) + ADR Phase 1 list.

## scope

- Delete `src/aeat/domain/schema/_extractor.py` (27 LOC, dead Protocol with no production callers).
- Remove `from ._extractor import Extractor` and `"Extractor"` from `aeat/domain/schema/__init__.py`.
- Update 3 docstrings (`_boe_extractor.py`, `_fetch.py`, `_models.py`) that referenced `~aeat.domain.schema.Extractor` cross-refs.

## pre-merge safety check

`grep -rn "schema.Extractor|schema._extractor|Extractor protocol" --include="*.py" .`: hits were:
- 3 docstring cross-refs (cleaned in this PR).
- `__init__.py:43` import + `__init__.py:81` `__all__` entry (removed in this PR).
- The defining file itself (deleted).

Zero production code uses the `Extractor` Protocol — no `extract()` callers run through it. The Protocol existed as an interface for "future extractors" that never materialised.

## verification

- `python -c "import aeat.domain.schema; assert 'Extractor' not in aeat.domain.schema.__all__"` — passes.
- `prek` pre-commit hooks — to be enforced on commit.

## next step

Phase-1 dead-code workstream **COMPLETE**. Step 2 closes after this PR merges. Step 3 begins next: 7 layered-violation untangling PRs (per research-doc Layered-architecture violations consolidated).
