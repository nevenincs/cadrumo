---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e832ce5f0146d7985258e27acafc5c4b5b177b6e7bf967df7143ec50a2af7442'
step_id: 'S03'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---




# Guard the rasterisation path with require_optional_extra immediately before its lazy import, red if the import raises ModuleNotFoundError instead of the typed refusal when the extra is absent

## Scope

- `src/cadrumo/adapters/outbound/llm/_providers/local.py`

## Description


## Outcome

## Verification


## Notes

