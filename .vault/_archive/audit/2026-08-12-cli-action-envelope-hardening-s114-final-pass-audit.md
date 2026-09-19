---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:bdacc660d7edf68e98b7102fb468700b6e1a0811936b7698e9ad55748bbcec94'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `S114 final independent PASS review`

## Scope

Independent current-tree review of `W05.P10.S114`: structural extraction of a
single nested registered verdict, callback and standalone terminal projection,
fail-closed zero/ambiguous behavior, and envelope-safe handling of actual
missing-optional-extra and malformed Pre303 producers.

## Findings

### s114-unified-boundary | low | PASS: nested verdicts and safe producer views are preserved end to end

The application projector traverses only Pydantic exception contexts and
Python causal links, admits exactly one registered typed verdict, and returns
no verdict for zero or multiple candidates. Callback and standalone terminal
paths use the same ordered boundary projection and generic no-recovery
fallback. A real blank `LLMRequest` retains the registered CLI validation code,
REFUSED category, exit 2, exact `llm.request.prompt_nonempty` evidence, null
action, `not_applicable`, and `operator_decision` in JSON and text for every
member of `SUPPORTED_OUTPUT_LANGUAGES`. Non-typed and two-candidate validation
retain `cli.validation.boundary_clean`.

Actual `MissingOptionalExtraError` and an actual lazily validated malformed
Pre303 section were exercised through both callback and standalone terminal
paths in every supported locale. The original registered class continues to
determine code, category, exit, retryability, and message key, while the
rendered envelope is constrained to the declared machine context. Optional
extra output carries only `extra`, `import_name`, and `importable`; Pre303
output carries only `section` and `validation_error_type`. Install commands,
feature prose, `install_hint`, full Pydantic detail, and producer prose are
absent. The action evidence remains the exact fact-only no-recovery verdict.

The terminal integration lane passed 12 tests. The callback, LLM model,
Pre303, and error-registry lane passed 33 tests. Ruff and formatting passed.
Focused BasedPyright passed with zero diagnostics for the application owner,
callback projector, and owned tests. A whole terminal-module invocation still
reports three diagnostics on unchanged parse-renderer lines introduced before
S114; blame and a zero-context diff prove none belongs to this change.

## Recommendations

- Keep S114 open only for the separately owned rehoming-ledger reconciliation
  and final plan lifecycle transition.
- Preserve the safe-view allowlist as exactly the two declared producer
  families; new families require their own typed facts and full callback plus
  terminal proof.
