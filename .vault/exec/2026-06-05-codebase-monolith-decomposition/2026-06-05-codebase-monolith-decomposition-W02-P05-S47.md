---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S47'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S47 - select residual ledger root closure groups

Scope: `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.

## Description

- Inspect remaining root `aeat app ledger` command registrations.
- Measure command and helper line lengths in `_ledger.py`.
- Run resident RAG search for ledger history/export/list/view/status/track and residual registrar candidates.
- Select import, lifecycle, and rule subgroups as focused extraction targets.

## Outcome

The import subgroup was selected because it owns provider validation, file/directory expansion, import-result aggregation, and validation output helpers. The lifecycle subgroup was selected because it owns transaction mutation command bodies. The rule subgroup was selected because it owns classification-rule registration and rendering helpers. All three can move behind CLI registrars while preserving application-layer behavior.

## Notes

The RAG include-path glob was retried with exact path filtering after PowerShell expanded the first glob invocation into positional arguments.
