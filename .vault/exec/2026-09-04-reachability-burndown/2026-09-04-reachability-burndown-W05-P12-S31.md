---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:d37794ab71ec95b7c60bf39d54bec8ab4e47bd5f72e9eb9922ce40c421e22dad'
step_id: 'S31'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve spec-table CLI bindings in the reachability walk: command handlers are bound through DeferredTarget(module, f"work_{name}") so the handler name exists only as an f-string and never as a literal, which reports live commands as unused; aeat app modelo work create, discard, list and status are all live while their handlers are findings

## Scope

- `dev/audit/unreachable_code.py`

## Changes

- `M` `dev/audit/unreachable_code.py`
- `M` `dev/audit/tests/test_unreachable_code.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `verify:` `uv run --no-sync pytest -q dev/audit/tests/test_unreachable_code.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/audit` -> `pass`

## Notes

The CLI command tables bind a handler through
`DeferredTarget(module, handler_name or f"work_{name}")`, where the leaf token
is declared in the same table. The module string is a literal and was already
read, which is why these modules were reachable, but the handler name exists
only after formatting, so every spec-bound command handler was reported unused
while its command was live. `aeat app modelo work create` runs; `work_create`
was a finding.

Subject resolution now derives the assembled names. The reader is narrow in
three ways, each guarding the direction that matters: a prefix counts only when
the f-string opens with a constant that is a valid identifier fragment ending in
an underscore, so a format string like `f"{count} rows"` contributes nothing;
tokens come only from string literals in the SAME module, so a prefix cannot
combine with a name declared elsewhere; and a token must match the command-leaf
shape. A looser reader would suppress real findings, which is worse than the
over-report it fixes.

Symbol findings fall 1107 to 1089. All 18 are live command handlers -- create,
discard, list, status, rename, calculate, observations, revision, revisions,
resume, run, run-details, runs, select and their siblings -- each confirmed
present in the live `--help` output before the change. Seven spent baseline
entries were removed; no entry was added.

No threshold, exclusion, baseline, skip or allowlist was widened. The scan was
taught to resolve a binding it could not previously follow.
