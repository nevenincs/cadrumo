---
step_id: "W04.P22.S423"
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

# W04.P22.S423 — SetupAnswers duplicate-class collapse

Deleted `application/wizard/_setup_answers.py` entirely (the class was the
file's sole content). Canonical `SetupAnswers` lives at `aeat.core.profile`.

Importers migrated (5 total):
- `application/wizard/_verifier.py`
- `application/wizard/test_verifier_checks.py`
- `application/wizard/test_verifier.py`
- `application/wizard/test_situacion_familiar.py`
- `application/wizard/test_monoparental_reduccion.py`
- `application/wizard/test_setup_answers.py` (relative import updated; per-field
  `pytest.raises` updated from `WizardAnswerTypeError` to `ProfileAnswerTypeError`
  since the core class raises the parent type)

**Files deleted:** `src/aeat/application/wizard/_setup_answers.py`
**Files touched:** 6 importer files
