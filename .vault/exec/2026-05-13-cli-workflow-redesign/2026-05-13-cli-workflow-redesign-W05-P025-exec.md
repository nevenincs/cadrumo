---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
step_id: 'W05.P025'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, function, or command, use inline `code`. -->

# `cli-workflow-redesign` `W05.P025`

Completed the thin CLI exposure phase for root help and discovery behavior.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_config.py`
- Modified: `src/aeat/entrypoints/cli/test_root_help_shape.py`

## Description

Exposed curated help and bare-root landing behavior through thin Typer
callbacks. The callbacks parse `--help`, read workflow state through
`workflow_state_repository`, call the backend operator surface help service,
and echo the returned presentation text. The CLI layer does not calculate
command inventory, source-kind vocabulary, lifecycle policy, or profile
semantics.

Closed plan rows: `W05.P025.S0145`, `W05.P025.S0146`,
`W05.P025.S0147`, `W05.P025.S0148`, `W05.P025.S0149`,
`W05.P025.S0150`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync ruff check src/aeat/application/operator_surface src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/test_root_help_shape.py`
