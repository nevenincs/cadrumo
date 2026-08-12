---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:93787f77ba5c96d422e102c417e62997948e8ce41cabdafd55070f45825a1297'
step_id: 'S114'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S114 and 2026-08-09-cli-action-envelope-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Unify shared CLI callback and terminal emitters around one typed projection mapping MissingOptionalExtraError and malformed aeat.pre303 CoreValidationError to exact machine-fact no-recovery outcomes through the CLI exception-precondition owner with no raw message matching or terminal bypass and ## Scope

- `src/cadrumo/application/cli_exception_preconditions.py`
- `src/cadrumo/entrypoints/cli/_common.py`
- `src/cadrumo/entrypoints/cli/_errors.py`
- `src/cadrumo/entrypoints/cli/_terminal_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

## Envelope-safe registered producer views

Final boundary review found that attaching the correct action was insufficient: rendering the original registered producer still allowed `feature`, `install_hint`, raw producer text, and full Pydantic validation detail to enter the envelope. The application owner now creates a narrow envelope view only for the two S114 families. It preserves the original registered class and therefore its canonical code, category, message key, retryability, and runbook identity, while replacing message resolution with the registry locale key and constraining context to declared machine facts.

Missing optional extras expose only `extra`, `import_name`, and `importable`; the live extra object, feature prose, install command, import exception fields, and raw message are removed. Malformed Pre303 configuration exposes only `section` and stable `validation_error_type`; the full validation rendering is removed. Callback projection computes the verdict from the original error before creating the safe view. Terminal projection likewise resolves from the original typed error and renders the same safe view, so neither path loses action identity or bypasses sanitisation.

The public callback tests use actual `MissingOptionalExtraError`, malformed Pre303 `CoreValidationError`, and real nested `LLMRequest` validation. They derive locale coverage from `SUPPORTED_OUTPUT_LANGUAGES`, assert exact code/category/action evidence, and assert prohibited context and producer tokens are absent. Zero-candidate and ambiguous multi-candidate Pydantic validation still fail closed to the generic validation condition.

Focused boundary, LLM-model, and registry verification passes 33 tests. Ruff and focused BasedPyright remain clean. A broader JSON-schema selection passes 359 tests; one separately owned profile-creation fixture fails before its schema assertion because it omits the newly required `tax-residence-jurisdiction-scope` input.

S114 remains open for independent review and ledger reconciliation.
