---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:d133ca879e0006062d75fca787f2928d2c67c322a03b01387b94be3b1cccdcf6'
step_id: 'S11'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---


# Resolve the Modelo nonwork CommandSpec pairs through their narrow shared declaration authority

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_common_command_parameters.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_calculations_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_filing_record_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_modelo_nonwork_calculations_command_specs.py src/cadrumo/entrypoints/cli/_modelo_nonwork_filing_record_command_specs.py src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py` -> `pass`

## Notes

Resolved through the non-work Modelo surface's own declaration authority, not the
ledger's. The two families' parameter shapes genuinely differ: the ledger spells
`metavar`, `count`, `eager`, `show_default` and `hidden` at every call while this family
relies on the dataclass defaults, and this family declares `is_flag=False` for its boolean
options where the ledger uses a bare presence switch. The ledger rewrite left these
untouched for exactly that reason, which is the shape guard working rather than an
oversight.

Eight factories were added to the existing shared parameter module, justified by a census
of the three clone-bearing modules: seven shapes account for 35 of their 44 literal
declarations. The remaining nine stay literal because they are distinct contracts --
transport loci, constrained paths, and domain enum values -- and folding them in would
have merged authorities that only look alike.

37 literals were replaced (16 calculations, 13 filing record, 8 reconcile). Contract
equivalence proven by canonical comparison of the three exported spec tuples: 4, 4 and 3
specs, `sha256:37cf4820c235480760e69d7b9d53a24783bbf8c7203fa58a293e2f2feccaa68c` on both
sides.

Clone count fell from 14 to 12; duplicated lines from 0.06% to 0.05%. The
modelo-nonwork-command-declarations cluster is fully resolved and no longer appears in the
ledger. All eight new factories have production consumers and the tree-wide unused-symbol
count is unchanged at 1414.

`test_modelo_describe_payload_parity::test_boundary_filing_years_remain_valid` fails in
this worktree; it was proven pre-existing by A/B against copies of the unmodified modules,
failing identically with and without this change. `test_root_command_specs` remains the
other known pre-existing failure.
