---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P307.S1837'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-s1837-code-review-audit]]"
---

# `cli-workflow-redesign` `W62.P307.S1837`

Enforced that `application/topics` remains backend catalogue code only, with no Typer application, command-local rendering path, or CLI entrypoint dependency.

## Description

The topic catalogue tests now include a structural AST invariant over the full `application/topics` package tree. Non-test topic modules must not import Typer, Click, Rich, CLI entrypoints, central emitters, or output-rendering helpers, and must not call print or echo. This preserves the accepted boundary: topic catalogue data is consumed by registry application services and exposed through `aeat app registry`, not through a parallel topic command or backend-local renderer.

## Review Remediation

Code review found the first invariant scanned only direct package children. The invariant now scans recursively and excludes tests and cache artefacts.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/application/topics`
- `uv run --no-sync ty check src/aeat/application/topics`
- `uv run --no-sync pytest src/aeat/application/topics/test_catalogue.py -q`

The focused topic catalogue suite passed with 5 tests.
