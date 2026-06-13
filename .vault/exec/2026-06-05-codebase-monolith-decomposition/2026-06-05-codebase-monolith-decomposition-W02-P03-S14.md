---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S14'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S14 - modelo slice selection

Scope: `src/aeat/entrypoints/cli/_modelo.py`.

## Description

- Ran exact discovery over `_modelo.py` Typer apps and command decorators.
- Ran exact discovery over filing-record, verification-report, amend, history, and reconcile test references.
- Restarted `vaultspec-rag` and ran semantic code search for modelo filing-record and verification-report command flows.
- Selected the filing-record plus verification-report command groups as the next modelo extraction slice.

## Outcome

The selected slice covered:

```text
filing_record_app
verification_report_app
filing_record_list
filing_record_show
filing_record_import
verification_report_list
verification_report_show
```

The group is backed by application-layer `list_filing_records`, `get_filing_record`, `import_external_filing_evidence`, `list_verification_reports`, and `get_verification_report`. Rendering helpers remain re-exported from `_modelo.py` for existing tests and consumers.

## Notes

The RAG service was stopped at the beginning of this step. It was restarted and semantic discovery succeeded before selection.
