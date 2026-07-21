---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S05'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Narrow diagnostics run-health adapter access to the outbound LLM package

## Scope

- `.importlinter`

## Description

- Search the code semantic index for the diagnostics run-health, LLM adapter, and import-linter wildcard boundary.
- Confirm the module's imports with targeted source search and a Python AST walk, then enumerate application, CLI, schema, and test call sites.
- Classify `cadrumo.adapters.outbound.llm` as the only live adapter dependency and as a strict descendant of the existing `cadrumo.adapters.**` allowance.
- Replace only the diagnostics run-health wildcard target with the public outbound LLM package; preserve every neighboring ignore and contract setting.
- Exercise the complete diagnostics run-health real-storage test module and rebuild all import-linter contracts without cache.

## Outcome

- Semantic search surfaced the import-ledger and architecture-reporting context; exact source inspection identified the live application module and its callers.
- The AST contains one adapter import: the level-two relative import of `adapters.outbound.llm` for `LLMRunRecord` and `LLMRunTelemetryRecorder`. Its only other project import is application auth. No `import_module`, `__import__`, `find_spec`, or string-dispatched adapter reach exists.
- Caller search found the diagnostics telemetry application consumer and the five lazy CLI handlers for run health, recent runs, latency, errors, and LLM usage. They call the diagnostics application API and do not introduce an alternate adapter path.
- `uv run --no-sync pytest -q -n0` on the diagnostics run-health test module passed `24` tests in `10.85s` against genuine encrypted secure-object storage.
- `uv run --no-sync lint-imports --no-cache` analyzed `3421` files and `16152` dependencies. All five contracts were kept, zero were broken, and strict unmatched-ignore alerting remained satisfied.

## Notes

- The change narrows an existing production construction/read boundary; it adds no second pin, dynamic loader, compatibility route, or broader production exemption.
- No source, test, or caller implementation changed.
