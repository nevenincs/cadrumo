---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S24'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# make bindings list --modelo a registry-derived click.Choice that refuses an unknown code with the accepted-codes set in the error message

## Scope

- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`

## Description

- Build a module-level `_MODELO_CHOICE` from `registry_modelo_codes()` (the registry-bound modelo id set), cast to the vendored-typer ParamType to bridge the static type duality.
- Wire `click_type=_MODELO_CHOICE` onto the `--modelo` option of both `bindings list` and `bindings preview`.
- Reference the choice through a module-level name because `from __future__ import annotations` stringifies the `Annotated` metadata carrying `click_type=...`, which Typer re-evaluates in the module global namespace where a closure-local binding is invisible.

Modified file: `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.

## Outcome

`bindings list --help` and `bindings preview --help` surface the accepted modelo-code set, and an unknown `--modelo` refuses at parse time naming the accepted codes, per the CLI-Choice-hint mandate. A direct `convert` probe confirmed a valid code (`303`) is accepted and `ZZZ` refuses with the accepted set; integration tests assert the help and refusal surfaces.

## Notes

A first attempt used a lazy-property `click.Choice` subclass referenced through a closure local; Typer's annotation evaluation could not resolve the closure name and the subclass rendered as a `FUNCTION` metavar without validating. The fix matches the established `_CONFIG_RESET_SCOPE_CHOICE` convention: a module-level `click.Choice` constant built once from the registry. The bundled registry load this triggers needs no secret passphrase.
