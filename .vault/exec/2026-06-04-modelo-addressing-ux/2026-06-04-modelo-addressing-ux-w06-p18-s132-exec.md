---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S132'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S132 CLI boundary classification matrix

Scope:
- `.vault/exec/2026-06-04-modelo-addressing-ux`

## Description

- Classify modelo CLI command responsibilities into parsing, rendering, backend calls, and business decisions.
- Identify which responsibilities must remain in CLI and which must move to backend services.

## Outcome

| Responsibility | Current location | Classification | Required destination |
| --- | --- | --- | --- |
| Typer option and argument declarations | `_modelo.py` | CLI parsing | CLI command modules |
| Typed envelope rendering | `_modelo.py`, `_modelo_payloads.py` | CLI rendering | CLI rendering helpers and payload schemas |
| Work target visible-key resolution | `_modelo.py`, `_selectors.py` | Business policy | `src/aeat/application/modelo` service boundary |
| Revision selector defaults | `_modelo.py`, `_selectors.py` | Business policy | `src/aeat/application/modelo` service boundary |
| Registry revision temporal selection | `_modelo.py` | Business policy | application/modelo work lifecycle service |
| Tax-rule input calculations | `_modelo.py` | Business logic | application/modelo calculation input services |
| Workflow profile loading for verify/file/export | `_modelo.py` | Application orchestration | application/modelo lifecycle services |
| Projection and compare arithmetic | `_modelo.py` | Business logic | application/modelo projection and comparison services |
| Reconcile/export service calls | `_modelo.py` | Application orchestration | application command wrappers |

## Notes

- CLI modules may translate boundary exceptions to CLI errors, but they must not decide legal, filing, calculation, persistence, or selector policy.
