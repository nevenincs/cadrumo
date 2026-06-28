---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S127'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S127 CLI module size and complexity inventory

Scope:
- `src/aeat/entrypoints/cli`

## Description

- Inventory production and test CLI Python modules with AST parsing.
- Count lines, functions, command decorators, maximum function length, and approximate compound nesting.
- Identify monolithic files and overgrown command handlers before mitigation.

## Outcome

Top risks:

| File | Lines | Functions | Commands | Max function | Max function lines | Nesting |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| `src/aeat/entrypoints/cli/_modelo.py` | 7115 | 117 | 44 | `work_calculate` | 545 | 7 |
| `src/aeat/entrypoints/cli/_ledger.py` | 4255 | 95 | 52 | `ledger_classify` | 194 | 4 |
| `src/aeat/entrypoints/cli/_config/__init__.py` | 2890 | 58 | 35 | `config_status` | 151 | 3 |
| `src/aeat/entrypoints/cli/_app_live.py` | 1856 | 38 | 24 | `iva_wallet_capture_remote_state_cmd` | 94 | 2 |
| `src/aeat/entrypoints/cli/_config/_google.py` | 1399 | 25 | 11 | `google_sync_calc_pull` | 171 | 3 |

`_modelo.py` is the immediate blocker for the current ADR because it combines command registration, parsing, rendering, natural-key selection, tax-rule flags, calculation input assembly, registry policy, filing workflow calls, projection, comparison, audit, and lifecycle helpers in one module.

## Notes

- No code was changed by this inventory step.
