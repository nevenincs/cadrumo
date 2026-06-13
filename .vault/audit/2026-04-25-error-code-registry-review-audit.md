---
tags:
  - '#audit'
  - '#error-code-registry'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - '[[2026-04-25-error-code-registry-plan]]'
  - '[[2026-04-25-error-code-registry-adr]]'
  - '[[2026-04-25-error-code-registry-research]]'
  - '[[2026-04-24-aeat-cli-wireframe-reference]]'
  - '[[2026-04-24-aeat-cli-wireframe-adr]]'
---

# `error-code-registry` Code Review

Status: `PASS`

Follow-up review pass for issue #398, applying the narrowed acceptance contract from the issue itself where it differs from the broader iteration-6 wireframe. I re-reviewed the scoped files only, ignored the unrelated user modifications in `.gitignore` and `.mcp.json`, and treated the issue's explicit acceptance for placeholder exit codes and the Step 3 `ErrorEnvelope` fields as authoritative for this branch.

Verification run on this worktree:
- `just lint` -> pass
- `just typecheck` -> pass
- `just test` -> pass (`2982 passed, 13 skipped, 24 deselected`)
- `just hooks` -> pass

What now holds against the narrowed #398 scope:
- The package conversion preserves the public `aeat.core.errors` surface, with non-public leaf modules re-exporting from there rather than introducing a second public error API.
- `ErrorCode` and `ErrorEnvelope` remain strict, frozen Pydantic v2 models.
- The registry is now an explicit declared catalogue. `_DECLARED_ERROR_CODES` and `_DECLARED_CODE_BY_QUALNAME` predeclare the public rows, and `bind_error_code()` now fails loudly when an `AeatError` subclass lacks a declared entry instead of synthesizing one from heuristics (`src/aeat/core/errors/_registry.py:103`, `src/aeat/core/errors/_registry.py:2017`, `src/aeat/core/errors/_registry.py:2023-2042`).
- Registry enforcement is materially stronger. The test now resolves raise targets through imported module namespaces, falls back to the known subclass index, and fails unresolved AEAT-looking error references instead of silently skipping them (`src/aeat/core/errors/test_registry_enforcement.py:56-75`, `src/aeat/core/errors/test_registry_enforcement.py:116-140`).
- The CLI boundary still preserves the intended runtime behavior: `AeatError` re-raises in test mode, writes the structured stderr payload, and exits through the accepted placeholder mapping (`src/aeat/entrypoints/cli/_errors.py:57-62`).
- The requested issue invariants remain covered: stderr-only error output, clean stdout, stable ASCII prefixes, default `es` language resolution with `AEAT_OUTPUT_LANGUAGE`, secret scrubbing, and the workflow `run` / `next` deferral from root decoration.

## 2026-04-25 follow-up findings

No remaining HIGH or CRITICAL findings in the scoped #398 work under the narrowed issue acceptance contract.

## Verdict

Pass. Safe to merge for issue #398 as scoped.

The two previously actionable blockers are addressed, and the remaining behavior matches the accepted contract for this branch: explicit declared registry rows, loud failure on undeclared subclasses, stronger raise-site enforcement, stable stderr emission, and a green gate chain. The broader iteration-6 taxonomy and envelope expansions remain valid follow-on context, but they are not blockers for this issue after the scope clarification.
