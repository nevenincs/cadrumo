---
step_id: S264
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S264

**Raise site:** `src/aeat/application/modelo/_actions.py:2413`

**Change:** Introduced `ModeloApplicabilityFilterError(ModeloError)` class at line ~864 in `_actions.py` (after `CasillaProvenanceMissingError`). Replaced `raise ValueError(f"Unknown applicability filter: {filter_name!r}")` with `raise ModeloApplicabilityFilterError(...)`.

**Registry:** Entry added to `core/errors/registry/_application.py` with code `REFUSED_MODELO_APPLICABILITY_FILTER`. Locale key `errors.refused.refused_modelo_applicability_filter` added to all 4 locale files (en, es, ca, hu) via `python -m aeat.locales set`.

**Note:** The registry entry and locale key were already in HEAD from a prior agent commit (S266 wave). The class introduction and raise-site migration are the new work here.

**Tests:** `test_survivor_envelope_enrollment.py::test_modelo_applicability_filter_error_enrolled` passes. `test_modelo_210_phase1.py` updated from `ValueError` to `ModeloApplicabilityFilterError`.

**Commit:** `d76cbf66e`
