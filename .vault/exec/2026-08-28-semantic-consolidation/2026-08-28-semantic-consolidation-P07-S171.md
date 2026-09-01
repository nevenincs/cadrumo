---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5502806f0b047917675ad2bef95e3743737c6055762cb22ea42b2b41b2bdf58a'
step_id: 'S171'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Guard every rewrite with a parse of the rendered source before writing, and widen the post-write damage scan to the dev root the rewriter was already writing to

## Scope

- `dev/quality/`

## Changes

- `M` the campaign's rewrite tooling: every write now parses the rendered source first and refuses rather than writing
- `M` the post-write damage scan now walks `src/` and `dev/`
- `verify:` 0 files fail to parse under either root; 0 unresolvable relative imports

## Notes

Raised by another session, with measurements this campaign did not have: at peak
`ruff check src/cadrumo` reported 3192 syntax errors from the automated import
rewrite, and named six files, of which `dev/locales/_fstring_registry.py` and
`src/cadrumo/tests/__init__.py` were plainly in this campaign's blast radius --
the first imports from `application.storage_management` and the second consumes
`tests.fixtures`, both retired here.

The splice bug itself was known and half-fixed: rewritten imports were written
over the original line range without preserving the original node's
indentation, which put a function-local import at column zero. That half was
found earlier, by pytest collection.

### The reporting gap was worse than the bug

The post-write damage scan walked `src/` only. The rewriter's roots are `src/`
AND `dev/`, so every file written under `dev/` went unverified, and this
campaign kept reporting "0 files fail to parse" while another lane watched the
error count climb into the thousands. The number was true about the subset it
measured and was reported as though it covered everything written.

That is the same failure this campaign has now recorded three times in other
forms -- a count reported about the wrong population -- and it is the reason the
peer saw it first.

### Both fixes

`ast.parse` on the rendered text before every write, raising instead of
writing. It costs microseconds against a rewrite already being performed, and
every one of the six reported breakages would have been refused at the source.

The damage scan now parses both roots. Module-existence checking stays scoped to
`src/`, because `dev/` is its own package root: resolving its relative imports
against `src/` produced 410 false positives the moment the scan was widened
naively, which would have traded a silent gap for a noisy one.

### A second-order effect worth recording

The peer reported that `lint-imports` currently evaluates ZERO contracts,
because it aborts on the first syntax error it meets and prints a single narrow
complaint rather than a tally. A layering gate in that state is
indistinguishable from a passing one. That is the same shape as the earlier
finding in this campaign that one stale ignore silently aborted the whole
contract set -- a gate that fails open on malformed input reports nothing and
reads as clean.
