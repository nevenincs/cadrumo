---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W31.P157'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W31.P157`

Asserted the no-shadow contract for the corpus-inspection CLI. Two
boundary tests live in `test_registry_corpus.py`.

## Description

`test_no_top_level_normatives_or_manual_root_verb_is_registered`
walks `src/aeat/entrypoints/cli/`, skips test files, and asserts no
source file registers a Typer / Click verb whose name is
`normatives`, `manual`, or `manuales`. Per the apex CLI ADR the
root accepts only `aeat config` and `aeat app`; the
`manuals` sub-Typer (registered inside `registry.py` under
`aeat app registry manuals`) is NOT a root verb and is allowed.

`test_no_parallel_registry_corpus_surface_exists` searches the CLI
tree for any `typer.Typer(...name="citations"...)` or
`typer.Typer(...name="manuals"...)` declaration outside the
canonical `_registry_corpus.py` module. The check passes today
because the wave's deliverable is the only such declaration.

Closed plan rows: `W31.P157.S0937`, `W31.P157.S0938`,
`W31.P157.S0939`, `W31.P157.S0940`, `W31.P157.S0941`,
`W31.P157.S0942`.

## Tests

Both boundary tests pass as part of the 11-test
`test_registry_corpus.py` suite.
