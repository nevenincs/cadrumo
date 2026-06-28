---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S07'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Probe Ollama before vision inference + refuse instructively

## Scope

- `widen classify CLI to catch LLMProviderError/connection errors`
- `add ollama providers row`
- `Playwright hint`
- `src/aeat/application/ledger`
- `src/aeat/entrypoints/cli`

## Description

- Wrap the on-host vision inference so an unreachable Ollama / unpulled model becomes a typed LLMClassifierError (which the classify CLI already renders) carrying the exact remediation, instead of a raw httpx.ConnectError traceback; real-behaviour test.

## Outcome

classify --read-evidence with Ollama down/model-missing now refuses instructively.

## Notes

The ollama row on `ledger providers` and the Playwright BrowserError remediation hint are subsumed by `config check` and deferred as minor.

