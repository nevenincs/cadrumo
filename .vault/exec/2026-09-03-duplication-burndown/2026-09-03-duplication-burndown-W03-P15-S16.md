---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:dc3bcbaf3d6dad9bc29b57e9f02d884c79685b12b9e30a22bee1a0fba670848b'
step_id: 'S16'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate the Ledger Renta binding declarations against registry authority and consolidate only their shared concept

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry -k "ledger_renta or gastos or binding"` -> `pass`

## Notes

No code change. Consolidating only the shared concept is what this Step permitted, and the
shared concept is already consolidated.

Both families already resolve through `_ledger_binding_resolution`, referencing
`resolve_ledger_family_binding_values` and `unsupported_ledger_family_observations` six
times each, and both already reach the shared `binding_aggregation`,
`binding_selector_utils` and `ledger_binding_selector_support` modules. There is no
remaining shared mechanic to centralise.

What must NOT be merged is the declarations themselves. The two carry different governing
authority: the estimacion directa family binds `Modelo.M100` and the pago-fraccionado
family binds `Modelo.M130`, over different casilla sets. Each relationship family is
required to keep its own typed declaration and resolver at its owning module, so merging
them would break the binding contract rather than remove duplication. A shared preamble is
not evidence of shared identity.

The detector's matched span is the import preamble, lines 7 to 30 in both files, naming
the shared registry vocabulary. It is the same artifact of correct centralisation already
adjudicated for the sede checker pair: the more mechanics move to shared modules, the
longer the identical import list grows.

664 registry tests pass. The group stays recorded and visible in the count.
