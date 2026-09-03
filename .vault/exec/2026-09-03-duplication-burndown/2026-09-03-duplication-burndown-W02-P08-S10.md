---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:9b4ee16992f9ba8a1e978a4b2904eac9a974166445a188f421f5a1c7c769aae9'
step_id: 'S10'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Consolidate the evidence, foundation, classification, and counterparty clone components with focused command graph proofs

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_foundation_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_classification_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_counterparty_command_specs.py`
- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py src/cadrumo/entrypoints/cli/_app_ledger_foundation_command_specs.py src/cadrumo/entrypoints/cli/_app_ledger_classification_command_specs.py src/cadrumo/entrypoints/cli/_app_ledger_counterparty_command_specs.py` -> `pass`

## Notes

88 literal parameter declarations were replaced (29 evidence, 29 foundation, 22
classification, 8 counterparty) by the same exact-shape AST rewrite used for the previous
component: a call is rewritten only when its keyword shape equals a primitive's exactly.

Contract equivalence proven by canonical comparison of the four exported spec tuples
before and after: 12 evidence, 8 foundation, 1 classification, 3 counterparty,
`sha256:408fe8dff0d130a122112fc6b6ad630624bb8277b200d6d3698223cc8cd618a4` on both sides.
The comparison sorts every set before rendering, because `repr` on a dataclass holding a
frozenset varies with the process hash seed.

Clone count fell from 37 to 14; duplicated lines from 0.15% to 0.06%. The
ledger-command-declarations cluster fell from 28 groups to 5.

The transient debt this campaign's earlier Step introduced is now fully repaid. All six
parameter primitives have production consumers, the support module reports no unused
symbols, and the tree-wide unused-symbol count returned to 1414 -- its value before the
primitives were defined.

The disposition ledger was reconciled against the live scan through its owning generator,
as the previous consolidation also required. 14 groups now carry a disposition.

The two CLI failures remain the pre-existing ones established by A/B in the previous
Step: `test_root_command_specs` and `test_ledger_interface_contract_payloads`. The passing
count in that selection is unchanged at 321.
