---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:4992439a0b4aa9b14621f587cb040291fd7cf55c07466235a71eb676360d56b6'
step_id: 'S01'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Derive a per-verb input schema from the CLI command registry click parameters, replacing the shared args bag

## Scope

- `src/aeat/entrypoints/mcp/_input_schema.py`

## Description

- Add `_input_schema.py` deriving a strict per-verb input schema from the live CLI command tree.
- Walk the Typer/click tree per operator-callable command key, threading a fresh child context at each level so lazily-loaded subcommand modules materialise exactly as under real dispatch.
- Project each leaf command's declared parameters into typed `VerbParameter` records: positional argument vs `--option`, JSON scalar type, requiredness, enum choices, multiplicity, boolean-flag shape, help text.
- Record the resolved command path as click names it (hyphenated leaf tokens) on `VerbInputSchema.cli_path`.
- Emit the JSON Schema object via `VerbInputSchema.json_schema` and reconstruct the `aeat` argv tail from named arguments via `cli_argv_for`.
- Add real-behavior tests exercising the derivation and argv mapping against the live CLI tree.

## Outcome

`build_verb_input_schemas` produces one non-bag object schema for all 231 exposable command keys. Positional arguments precede options in the reconstructed argv, multiple parameters repeat their token, boolean flags emit only their flag, and enum choices surface in the schema. The resolved `cli_path` carries the hyphenated command name click dispatches on (`iva-wallet`, not the underscored key segment `iva_wallet`), so a downstream dispatcher builds an argv that actually resolves. Ruff check/format clean, pyright clean, and `pytest src/aeat/entrypoints/mcp` green at 47 passed.

## Notes

Two Typer-vendored-click hazards surfaced and were handled: `isinstance` against the top-level `click.Argument`/`click.Group` classes misclassifies Typer's vendored types, so parameter kind keys on the stable `param_type_name` marker and the tree types come from `typer._click.core`. One registry command key (`config.bucket.history`) does not resolve to a live command and falls back to an empty-parameter schema over the naive path rather than crashing the build. Custom Typer enum converters (`FuncParamType`) do not expose their choice set, so those parameters are typed as plain strings without an `enum` rather than fabricating a choice list; the CLI still validates them server-side.
