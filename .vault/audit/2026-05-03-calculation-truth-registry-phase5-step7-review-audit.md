---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step7-exec]]'
---

# `calculation-truth-registry` Code Review

CALC-STEP7-001 | LOW | Stale formula/ruleset wording remained in export comments

Initial review found stale legacy terminology in `modelo_303_2025.py` and
`_record_spec.py`. The wording did not reintroduce a runtime dependency, but it
weakened the cleanup claim by continuing to describe export schema work in terms
of the deleted formula/ruleset authority.

Resolution:

- Rewrote the 303 2025 module docstring to describe the registry-backed Modelo
  definition.
- Rewrote record-spec comments and argument docs to describe Modelo casilla
  mappings and compact registry declaration style.
- Re-ran repo search over touched export files and the DR303 fixture for stale
  formula/ruleset terms.
- Re-ran ruff, ty, and focused pytest.

Follow-up review result:

- No findings.
- Reviewer confirmed forbidden formula package terms only remain in deletion-gate
  assertions, not runtime paths.

Residual risk:

- The deleted formula-dependent export/schema alignment tests do not yet have a
  registry-backed replacement. This is intentional for the deletion slice but
  must be closed by a later registry-to-export completeness test.
