---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:52727d3533b41241ad9043490023c65d985d897dac16d44dddf57ca437869003'
step_id: 'S114'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Unify shared CLI callback and terminal emitters around one typed projection mapping MissingOptionalExtraError and malformed aeat.pre303 CoreValidationError to exact machine-fact no-recovery outcomes through the CLI exception-precondition owner with no raw message matching or terminal bypass

## Scope

- `src/cadrumo/application/cli_exception_preconditions.py`
- `src/cadrumo/entrypoints/cli/_common.py`
- `src/cadrumo/entrypoints/cli/_errors.py`
- `src/cadrumo/entrypoints/cli/_terminal_errors.py`

## Description

- Traverse Pydantic `ValidationError` context errors and Python causal chains structurally.
- Admit exactly one registered typed error carrying a valid terminal verdict and fail closed otherwise.
- Map missing optional extras and malformed `aeat.pre303` configuration to fact-only no-recovery verdicts.
- Route both callback and terminal error emitters through the same typed projection.
- Prove real `LLMRequest` validation, ambiguity, generic validation, and declared S114 producer families through the command boundary.

## Outcome

Nested application errors no longer lose their canonical precondition when Pydantic wraps them. The generic validation boundary retains its registered error identity while its action member carries the exact nested verdict. Zero typed candidates and multiple typed candidates retain the generic `cli.validation.boundary_clean` outcome. Missing optional extras expose only extra/import identity and `importable=false`; malformed Pre303 configuration exposes only section identity and `valid=false`. Neither mapping uses exception messages, English fallbacks, or command prose.

## Notes

Fresh VaultSpec RAG discovery located the generic validation projector, policy projection reader, terminal emitter, LLM validator carrier, and application provisioning condition before implementation. Exact source confirmation found one callback ValidationError projector and one terminal crash emitter.

Focused public boundary verification passes 15 tests, including ca/en/es/hu nested `LLMRequest` projection and fail-closed zero/multiple cases. The combined boundary and LLM model lane passes 18 tests. Ruff passes and focused BasedPyright reports zero diagnostics.

A broader 39-case boundary, LLM-model, and registry selection produced 36 passes and three unrelated fixture failures before the exercised boundary: `test_errors_boundary.py` constructs `UserProfileRecord` with retired schema version 1 while the canonical version is 5. The failure is recorded without weakening validation or modifying that separately owned fixture.

S114 remains open for independent review and ledger reconciliation.

## Static typing closure

The final S114 `ty` audit found three test/projection typing ambiguities without runtime failures. Envelope-safe context now materialises an explicitly typed dictionary before assignment. Terminal fail-closed cases accept an actual zero-argument callable. Callback ambiguity cases parameterise the validation callable itself, separating `BaseModel.model_validate` from `TypeAdapter.validate_python` rather than using a model/adapter object union.

The exact six-file S114 `ty check` reports all checks passed with no ignores, broad `Any`, or compatibility shim. Terminal integration remains 12/12 and callback/LLM/registry verification remains 33/33. Ruff and formatting pass.

S114 remains open for independent review and ledger reconciliation.

## Terminal nested-validation parity

The standalone terminal previously attempted only direct `CadrumoError` unwrapping. An escaped Pydantic `ValidationError` therefore became `CliUnexpectedBoundaryError` even when its structural context contained one registered LLM refusal. The terminal now calls the same ordered boundary projector as callbacks, then applies the same generic no-recovery fallback when no unique typed candidate exists.

A real `LLMRequest` blank-prompt validation is exercised through `run_standalone_with_error_contract` in JSON and text modes for every `SUPPORTED_OUTPUT_LANGUAGES` member. It retains `REFUSED_CLI_VALIDATION_BOUNDARY`, category `REFUSED`, the exact `llm.request.prompt_nonempty` evidence and terminal outcome, and refusal exit code rather than INTERNAL exit 6. Real non-typed validation and a two-error Pydantic aggregate prove fail-closed `cli.validation.boundary_clean` behavior. Existing callback producer, LLM-model, and registry coverage remains green.

Verification: terminal boundary integration passes 12 tests; the callback/LLM/registry lane passes 33 tests. Ruff passes.

S114 remains open for independent review and ledger reconciliation.

## Envelope-safe registered producer views

Final boundary review found that attaching the correct action was insufficient: rendering the original registered producer still allowed `feature`, `install_hint`, raw producer text, and full Pydantic validation detail to enter the envelope. The application owner now creates a narrow envelope view only for the two S114 families. It preserves the original registered class and therefore its canonical code, category, message key, retryability, and runbook identity, while replacing message resolution with the registry locale key and constraining context to declared machine facts.

Missing optional extras expose only `extra`, `import_name`, and `importable`; the live extra object, feature prose, install command, import exception fields, and raw message are removed. Malformed Pre303 configuration exposes only `section` and stable `validation_error_type`; the full validation rendering is removed. Callback projection computes the verdict from the original error before creating the safe view. Terminal projection likewise resolves from the original typed error and renders the same safe view, so neither path loses action identity or bypasses sanitisation.

The public callback tests use actual `MissingOptionalExtraError`, malformed Pre303 `CoreValidationError`, and real nested `LLMRequest` validation. They derive locale coverage from `SUPPORTED_OUTPUT_LANGUAGES`, assert exact code/category/action evidence, and assert prohibited context and producer tokens are absent. Zero-candidate and ambiguous multi-candidate Pydantic validation still fail closed to the generic validation condition.

Focused boundary, LLM-model, and registry verification passes 33 tests. Ruff and focused BasedPyright remain clean. A broader JSON-schema selection passes 359 tests; one separately owned profile-creation fixture fails before its schema assertion because it omits the newly required `tax-residence-jurisdiction-scope` input.

S114 remains open for independent review and ledger reconciliation.

## Coordinated canonical rehoming reconciliation

A fresh read-only derivation established three identical stability boundaries separated by at least sixty seconds. Immediately before mutation, the canonical guard revalidated the ledger, plan, all-source, rendered postimage, structural-delta, and locator-delta hashes byte-for-byte. OWNER_ZERO was zero and every one of the twenty-four structural additions had exactly one open owner. The delta contained thirty-five removals, no historical-row, disposition, or current-identity changes, and 144 locator-only refreshes recorded as incidental metadata.

Exactly one S50 canonical-tool write produced the proven postimage. The resulting ledger SHA-256 is `bc6ddc3b5edddd852a155e48ca58ec6e3aa188f716cecef8615b9bef20de2aec`. Direct validation returned `E_REHOMING_VALIDATED:238`; the single immediate no-write replay returned `E_REHOMING_MIGRATION_CHECKED:238`. No second locator chase or write was performed. The complete canonical rehoming lane passed 74 tests.

This owner Step remains open for independent review and ledger reconciliation.
