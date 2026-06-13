---
step_id: "W04.P22.S427"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta8
commit: e7f96f6ec
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# W04.P22.S427 — FinancialProvider corpus attribute enforcement

Added `__init_subclass__` on `FinancialProvider` ABC. Runs once per concrete
subclass at class-definition time (import), enforcing:
- `verification_source` must be declared and one of the three valid literals
- `provisional_pending_specimen` must be declared as `bool`
- `no_corpus` providers must have `provisional_pending_specimen=True`

Abstract subclasses are skipped (guarded by `__abstractmethods__`). All 4
existing concrete providers (`_csv`, `_ofx`, `_xlsx`, `_pdf_n26`) pass
enforcement without change — they already declared both attributes correctly.

The `@property @abstractmethod` approach was rejected because all existing
providers use class-variable assignment syntax; `__init_subclass__` achieves
the same enforcement without changing the declaration pattern.

**Files touched:** `src/aeat/adapters/inbound/financial/providers/_base.py`
