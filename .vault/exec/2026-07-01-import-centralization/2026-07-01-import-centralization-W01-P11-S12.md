---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:7bbca2dc7e973e69bbe949f9167dad0ddb0bbe34467d46c8e82178ab9fd678ec'
step_id: 'S12'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `M111_NO_RETENCIONES_PROFILE_PATH`, `MaritimeExemptionResult`, `m111_no_retenciones_periods_for_bucket` to `aeat.application.calculations.__all__` with eager re-exports so the 4 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/application/calculations/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Promote `M111_NO_RETENCIONES_PROFILE_PATH`, `MaritimeExemptionResult`, `m111_no_retenciones_periods_for_bucket` to `aeat.application.calculations.__all__` with eager re-exports so the 4 existing cross-package consumer site(s) can import from the facade.
- Tie this row to the `application.live` / `domain.iva_compensation` / `application.calculations` W01 facade-promotion batch, landed in `2590a235f6` and recorded by the existing `W01.P05.S04` exec record.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded live import probes for the three facades, `ruff check`, `pytest --collect-only -q src/aeat`, and a 651-test targeted slice green. The W01 scaffold pass removed $(W01.P11.S12.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
