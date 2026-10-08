---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:9999f7dc44dc7e7dfe3bc8060c902735bb31628beb8d35fb6473eb4895db1646'
related: []
---

# `tui-entrypoint-separation` audit: `p01 capability teardown`

## Scope

Inspect the TUI capability teardown for stale CLI declarations, locale keys and root options left after removing the global launch path.

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

Remove the orphaned TUI_NOT_IMPLEMENTED code and locale/help keys. Remove --self-test from the root command or move it under aeat app tui with its behavior and help, as required by the identified gap.
