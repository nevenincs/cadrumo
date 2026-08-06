---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:830ab42a771cc8ef1d5ecf299b85dd9a174916024850733ba7315ecc97c10a50'
step_id: 'S02'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Reject an as_of argument on the unscoped registry discovery path with an instructive refusal naming the scoped form that honours it

## Scope

- `src/cadrumo/application/modelo/_registry_discovery.py`

## Description

- Add the facade helper `_refuse_unscoped_as_of(as_of, scoped_form)`: when `as_of` is supplied it raises `RegistryValidationError` with an operator-facing message naming the scoped query that honours as_of.
- Call it at the top of every unscoped discovery facade before the service call: `registry_describe_modelo` (names `registry_describe_modelo_for_scope`), `registry_casillas` (`registry_casillas_for_scope`), `registry_casilla` (`registry_casilla_for_registry_scope`), `registry_bindings` (`registry_bindings_for_year`), and `registry_formulas` (`registry_formulas_for_scope`).
- Import `RegistryValidationError` through the registry package facade.

## Outcome

The operator's first instructive surface now refuses `as_of` on the unscoped discovery path and names the exact scoped form that honours it, instead of the previous silent-ignore. The `*_for_scope` / `*_for_registry_scope` / `*_for_year` facades are untouched and still honour `as_of`. This is the application-boundary companion to the P01.S01 domain refusal (the safety backstop): a non-facade consumer still hits the domain refusal, while the CLI operator gets the scoped-form guidance. 57 CLI registry integration tests pass; ruff clean.

## Notes

git-diff-gated `_registry_discovery.py` clean at HEAD before editing. `registry_formulas` was included beyond the four originally-obvious verbs because it is also an unscoped discovery facade — leaving it would keep one silent-ignore lie. Two-layer refusal (facade operator-message + domain backstop) follows the same instructive-refusal-plus-defence-in-depth shape as the binding-validation discipline.
