---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:ee5687c2e2d07eb72de20263de284b06c2d86e486a595114679ab45aa80b2389'
step_id: 'S50'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Correct the wallet diagnostic field docstring so it stops overstating the capture scope relative to the implementation, gated by the generated environment reference regenerating without drift

## Scope

- `src/cadrumo/core/_config_integration_fields.py`

## Description

## Outcome

Landed in `fe527508fe`, confirmed at HEAD. The Step text names `src/cadrumo/core/_config_integration_fields.py`; the field actually lives in `src/cadrumo/core/config.py:519-536` (`cadrumo_wallet_diagnostic_dump_dir`). The description no longer claims "full captured page tree" or "may contain live taxpayer amounts" — it now states the capture is a "redacted structural-shape summary" (URL without query, element counts, form action paths, a content hash) and explicitly "never writes raw HTML, frame HTML, screenshots, input values, or wallet amounts." File-path correction noted here since the Step row cites the wrong file (see S105's record for the inverse mismatch — the two Steps' file citations appear swapped at authoring time).

## Notes
