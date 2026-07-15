---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S01'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Re-anchor the invocation-token regex on the real aeat executable so documented aeat invocations are scanned again, fixing the rename-sweep vacuity

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Rename `_CADRUMO_TOKEN_RE` to `_AEAT_TOKEN_RE` and re-anchor its pattern from the bare `cadrumo` token to the `aeat` executable token (`(?:^|[\s$|&(;])aeat(?=\s|$)`).
- Sweep the three usage sites (the module-level regex, `_parse_command_line`, `_cited_commands`).
- Rewrite the module docstring to state that `aeat` is the sole human CLI executable and that the `cadrumo` package / `cadrumo-mcp` server / `cadrumo-vault` / `src/cadrumo` paths are product references outside the gate's scope, recording the rename-sweep vacuity this repair fixes.
- Align the version-echo comment, the `_CitedCommand` docstring, the resolved-path violation messages, the context `info_name`, and the parametrised test docstring/message from `cadrumo` to `aeat`.

## Outcome

The conformance gate anchors on the real `aeat` executable token. Where it parsed almost nothing (docs cite `aeat` ~688 times, `cadrumo` never as a CLI invocation), it now decomposes and validates real invocations. Lint (`ruff`) and type check (`ty`) pass on the file.

## Notes

Deliberate scoping decision: the gate anchors on `aeat` only, not also on `cadrumo`. Per `cadrumo-product-authority-names`, `aeat` is the one human CLI executable; the `cadrumo` tokens in docs are package / MCP-executable / storage / path references (`cadrumo-mcp`, `cadrumo-vault/`, `src/cadrumo/`, prose "`cadrumo` uses"), never CLI lines. Scanning them as CLI invocations would only manufacture false positives from prose. No stale-brand `cadrumo <verb>` invocations exist in the surface.
