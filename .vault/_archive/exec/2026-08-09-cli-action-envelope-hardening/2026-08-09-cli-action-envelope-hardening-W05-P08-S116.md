---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c2840d5ff7d92bfb4a4cb472ebb03a05bd7a447b08f0e5c8e9f0243abababb80'
step_id: 'S116'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
## Scope

- `src/cadrumo/entrypoints/cli/_app_contract.py`
- `src/cadrumo/entrypoints/schema_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_app_contract_resilience.py`
- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Replaced package and filename discovery with the single immutable result-schema owner declaration.
- Imported only declared owner modules when materialising the result-schema registry.
- Removed CLI result-schema English fallback prose so rendering resolves through locale keys and typed facts.
- Proved declaration-to-decorator-owner and declaration-to-registry projection equality with production imports.
- Replaced the fresh-process profile-schema guard's independent owner literal with a declaration-derived owner selected from the registered profile-schema producers.
- Removed the guard's remaining owner-table redeclaration in favour of canonical result-schema module declaration terminology.

## Outcome

- The declaration covers every production `@register_schema` owner and each declared module contributes registered schema output.
- The S116 resilience gate passed, and the exact integration live-leaf-to-registry conformance gate passed.
- Both fresh-process profile-schema guards passed: the declared owner imports both profile schemas, and blocking that same derived owner drops both from the contract surface.
- The real console command `aeat --language en app contract` and its `es` equivalent both completed successfully, each reporting 308 registered commands with locale-specific summaries.
- Ruff formatting and lint passed for the four assigned Python files; the final terminology-only correction passed targeted Ruff and diff checks.

## Notes

- Execution is review-ready; `W05.P08.S116` remains open for independent review and is not closed here.
- File-scoped basedpyright reports the pre-existing `_emit_envelope` private-use and Typer callback unused diagnostics in `_app_contract.py`; both are present in `HEAD`.
- The default unit marker deselects the live symmetric gate; it passed when run with its required `integration` marker.
