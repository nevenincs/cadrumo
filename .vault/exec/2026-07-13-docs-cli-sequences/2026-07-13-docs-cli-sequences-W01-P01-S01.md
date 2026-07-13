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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Re-anchor the invocation-token regex on the real aeat executable so documented aeat invocations are scanned again, fixing the rename-sweep vacuity and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
