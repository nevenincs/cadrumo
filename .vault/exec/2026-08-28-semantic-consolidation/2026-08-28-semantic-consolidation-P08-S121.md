---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4fd1efb88356d5c45f62535ac8778dd0e14856e4067fedcff9b282c16ca148d7'
step_id: 'S121'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the dotted module paths written inside string literals, a class every AST sweep is blind to and which had been failing four custody lock tests in a way that read as flakiness

## Scope

- `src/cadrumo/`
- `dev/quality/namespace_retirement_sweep.py`

## Changes

- `M` 13 modules across `src/cadrumo/` and `dev/`
- `M` `dev/quality/namespace_retirement_sweep.py`
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/custody -n 0` -> `pass` (238, was 234 with 4 failing)

## Notes

Four custody lock tests were failing with "holder subprocess exited with code 1
before signalling ready" and "supervised child produced no readiness line".
Read as flakiness on this worktree's backing share, including by this campaign.
They were not flaky: the subprocess source is built as a STRING, and it named
`custody._filesystem`, a module an earlier retirement had made public. The child
died on ImportError and the parent could only report that it never spoke.

A dotted module path in a string is not an import node, so every AST sweep here
was blind to it. Twenty-six such paths were stale, in logger names, caplog
targets and spawned-subprocess sources.

The sweep arm added for this repeated the absence-assertion trap in its dotted
spelling: it rewrote `import_module("...._closure")` inside a
`pytest.raises(ModuleNotFoundError)`, inverting the test into asserting the live
module is absent. The arm now skips a path whose surrounding lines expect an
import to fail.
