---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:10a9796942b7fee4ac808d2dcc9d7c3bc1d539ee9f18ea7c1f0d36932ab72af8'
step_id: 'S33'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Give the module ratchet a verifiable disposition for capability a production contract requires but no entrypoint reaches: the classification ledger had already adjudicated domain.contabilidad and domain.is_compensation as staged capability, but the intentional kind enum held only design_time_authority, so the sole way to record them was widening allowed; add declared_by_contract, which must name the declaring file and is refused on load when that file stops naming the module, and close the hole the shared enum opened in the symbol ratchet where no declared_by exists to check

## Scope

- `dev/quality/unreachable_module_ratchet.py`

## Changes

- `M` `dev/quality/unreachable_module_ratchet.py`
- `M` `dev/quality/unreachable_module_ratchet.toml`
- `M` `dev/quality/unused_symbol_ratchet.py`
- `A` `dev/quality/tests/test_declared_by_contract_dispositions.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests dev/audit/tests -q` -> `pass`

## Notes

The module ratchet still reports `cadrumo.application.ledger.import_preparation`.
It is deliberately left red rather than dispositioned: its only declarer is the
dev capability matrix, and the TUI import door that would consume it can never
open, so a `declared_by_contract` entry would quiet a module whose contract is
itself unsatisfiable. That decision remains `W05.P12.S28`.
