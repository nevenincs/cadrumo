---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S26'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S26 - residual live verify selection

Scope: `src/aeat/entrypoints/cli/_app_live.py` and live CLI tests.

## Description

- Checked `vaultspec-rag` service health before semantic discovery.
- Ran exact discovery over remaining live command groups and related tests.
- Ran semantic discovery for live verify command extraction.
- Selected `app live verify` because it is a coherent sub-app with existing read-subgroup integration coverage.

## Outcome

Selection completed. RAG ranked `verify_latest`, `verify_nif_iva`, `verify_tgvi`, and `verify_list` as coherent extraction candidates.

## Notes

The live verify surface is a CLI adapter over `application.live.VerifyService` and AEAT Sede drivers; the extraction did not change live-read policy.
