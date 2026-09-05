---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:46d026aff12be8c4be86290e564d6175ef02bd7ad21097e57b008633c64168f0'
step_id: 'S18'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Run duplication, import, semantic, architecture, type, lint, focused, and full quality gates without threshold or exclusion changes

## Scope

- `dev/audit/.runs`

## Changes

- `M` `dev/quality/suite.py`
- `M` `dev/quality/tests/test_suite_gate_table.py`
- `verify:` `uv run --no-sync python -m dev.audit.duplication` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.dead_code` -> `pass`
- `verify:` `uv run --no-sync just check-semantic` -> `pass`
- `verify:` `uv run --no-sync ruff check .` -> `pass`
- `verify:` `uv run --no-sync ruff format --check .` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`
- `verify:` `uv run --no-sync lint-imports` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.relative_imports` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.suite` -> `fail, 2 of 12 gates, both peer-owned`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `fail, peer-owned`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail, peer-owned`

## Notes

Re-measured against the current tree; the earlier record for this Step was
taken at a revision whose results have since inverted in both directions, so it
is replaced rather than appended to.

Green: the duplication runner at 10 clones and 0.05 percent with every group
carrying exactly one disposition and zero uncovered, which is the closure the
amended governing decision defines; the dead-code audit; the semantic leak
screen; whole-tree lint and format; types; both import gates; and the docstring,
unconsumed-export and write-path ratchets. The aggregate suite reports 10 of 12.

Red, both peer-owned and both already classified: the module ratchet on three
modules that fit no available disposition, and the symbol ratchet on two
symbols. The owner decisions those need are tracked in the reachability plan and
are not resolvable from here.

Two gates were found running different arguments in the aggregate suite than in
their own justfile recipe, which is how a gate defined twice fails: the recipe
and the table disagree in silence. The dependency gate scanned the harness
package in the recipe but not in the table, so the table reported two
dependencies as declared-but-unused when both are imported there; widening the
table's scan to match removed both findings and surfaced no new ones. The
architecture gate ran four test files in the recipe and two in the table, so two
architecture gates never ran in the aggregate at all. Both were aligned to their
recipe, and a gate now compares each table entry's arguments against its recipe.

One transient was observed and is not a finding: the suite recorded a syntax
error in a locale test that a peer was rewriting during the run. The file parses
and the gate exits 0 on re-measurement.

No threshold, exclusion, baseline, skip or allowlist was changed. The dependency
scan was widened, which makes the gate see more rather than tolerate more.
