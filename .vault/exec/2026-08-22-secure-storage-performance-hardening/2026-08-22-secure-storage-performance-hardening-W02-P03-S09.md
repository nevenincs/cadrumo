---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:817714edd18f4e7bebaa63bc6e1f6a11668f7e53ccfbfb76afd3c378d9dd4857'
step_id: 'S09'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Refactor lazy registration into a reusable node loader with explicit targets and fail-loud dependency classification

## Scope

- `src/cadrumo/entrypoints/cli/_command_suggestions.py`

## Description

- Replace opaque import closures with immutable import and factory targets that
  expose stable ownership and validate the resolved Typer node.
- Resolve selected command paths token by token and give nested lazy groups an
  explicit registry key independent of their displayed operator token.
- Classify only exact, explicitly declared missing modules as optional and keep
  the canonical optional-extra inventory deferred until an import actually
  fails.
- Refuse duplicate registrations, invalid targets, required dependency defects,
  and internal or transitive optional-package defects without fallback.
- Drain exhaustive consumers through the real vendored Click command graph so
  nested lazy descendants cannot disappear from full-tree gates.
- Migrate root command targets and dynamic profile-wizard leaves onto the shared
  kernel without converting the remaining eager subtrees assigned to later
  Steps.
- Add real-import fixtures and focused gates for exact target loading, sibling
  exclusion, repeated materialization, callback and policy identity, required
  and optional failures, nested resolution, nested exhaustive materialization,
  and deferred optional-inventory loading.

## Outcome

The command-loading boundary now has one reusable kernel for module-backed and
runtime-built nodes. Each module-backed loader declares its module, attribute,
relative-import package, optional dependency provider, and child registry key.
Resolution imports only the selected token chain; exhaustive consumers traverse
the same `list_commands` and `get_command` protocol as dispatch. Cached Click
commands preserve callback and execution-policy identity across repeated
resolution.

Optional degradation requires exact equality with a declared
`ModuleNotFoundError.name`. Missing required dependencies retain their original
exception as the cause of the typed refusal. Missing transitive dependencies and
missing internal modules inside an installed optional package fail loudly. The
canonical optional-extra model is not imported during bootstrap registration.

Scoped Ruff and `ty` checks passed. The focused lazy-loader, command census,
policy identity, required/optional import-failure, manager-routing, and wizard
lanes passed 34 tests. Exhaustive JSON-schema and operator-surface consumers
passed 309 integration tests. Root and config help rendered successfully.
Independent review found two HIGH defects in the first pass: dotted optional
descendants could degrade and the legacy full materializer missed nested Click
nodes. Both were corrected, directly regression-tested, and approved on
re-review with no open findings.

## Notes

One broader documented-command conformance run passed 646 cases before stopping
on an unrelated concurrent workstation-sequence reference to the absent
`aeat app agent` command. The S09-owned exhaustive schema and operator-surface
modules were rerun independently and passed all 309 cases. No production
fallback, compatibility shim, or eager subtree conversion was left behind.
