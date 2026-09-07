---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:34f98339730bb5825af28f1a5977e4c0043b6fa6d92169a2fd025e84fa7e4721'
step_id: 'S107'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the fifth findings-discarding narrowing (is_active_censo_modelo) and gate the whole class with dev/quality/narrowing_delegators

## Scope

- `justfile`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/censo_modelos.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py`
- `A` `dev/quality/narrowing_delegators.py`
- `A` `dev/quality/tests/test_narrowing_delegators.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `justfile`
- `verify:` `just check-narrowing-delegators` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_narrowing_delegators.py src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.docstring_reference_ratchet` -> `pass`

## Notes

The detector was wrong before it was right, and both false positives were
caller-search scoping. Its first run reported four offences; three were real
callers it could not see. `check_m303_annual_orden_manifest` is imported and
called by `dev/registry/analysis/m303_orden_anual.py`, which the scan never
looked at because it searched only the tree that ships the definitions.
`generate_m303_annual_orden_manifest` and `read_total_system_memory_bytes` are
called from inside their own defining modules, which the scan skipped on the
assumption that an owner cannot be its own consumer. Both scoping rules are now
regression-tested rather than merely fixed.
