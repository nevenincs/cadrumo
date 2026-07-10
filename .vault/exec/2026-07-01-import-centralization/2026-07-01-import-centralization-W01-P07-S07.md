---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S07'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `TEXT_VALUE_GROUP`, `extract_pages_text_concatenated`, `extract_pages_text_from_bytes`, `extract_pages_text_from_path`, `extract_pages_text_with_fast_path`, `sha256_file`, `source_pdf_reference_path` to `aeat.adapters.inbound.pdf.__all__` with eager re-exports so the 14 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/adapters/inbound/pdf/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Promote `TEXT_VALUE_GROUP`, `extract_pages_text_concatenated`, `extract_pages_text_from_bytes`, `extract_pages_text_from_path`, `extract_pages_text_with_fast_path`, `sha256_file`, `source_pdf_reference_path` to `aeat.adapters.inbound.pdf.__all__` with eager re-exports so the 14 existing cross-package consumer site(s) can import from the facade.
- Tie this row to the adapters inbound PDF promotion recorded by the existing `W01.P03.S02` exec record and landed in `dedd12eb8`.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded direct facade-resolution probes, ruff checks, and clean `pytest --collect-only -q src/aeat` from the umbrella record. The W01 scaffold pass removed $(W01.P07.S07.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
