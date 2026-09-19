---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:fbbeea622e2432834a4f68156b64fc9ddf7e16bd72fb30d982a0d16b6be8b23d'
related: []
---

# `tui-entrypoint-separation` audit: `p01 capability teardown`

## Scope

## Findings

### retired-tui-refusal-contract | medium | The removed CLI refusal still has a live registry declaration and locale entries

`CliTuiNotImplementedError` was removed from `src/cadrumo/entrypoints/cli/errors.py`, but
`src/cadrumo/core/errors/registry/_entrypoints.py` still declares its
`TUI_NOT_IMPLEMENTED` code. Resolving every entrypoint declaration directly reports that
qualname as missing. The corresponding `errors.refused.refused_tui_not_implemented` locale
key remains in each shipped locale, as do the now-unreferenced root help keys
`cli.root.tui_help` and `cli.operator_surface.help.root.section_frontend_options`. This leaves
P01.S04 incomplete and retains the retired global-request vocabulary in the product locale and
error authorities.

### stale-root-self-test | medium | The root retains a full-screen self-test option whose value is now ignored

`src/cadrumo/entrypoints/cli/_root_command_specs.py` still registers `--self-test` with
`cli.root.self_test_help`, whose copy promises to start the full-screen interface. The matching
`self_test` parameter in `src/cadrumo/entrypoints/cli/_root_cli.py` is no longer read after the
global TUI launch path was removed. The option therefore succeeds without performing its documented
full-screen action. It must be removed with the global request or rehomed, with its behavior and
help, on the forthcoming opaque `aeat app tui` launcher.

## Recommendations
