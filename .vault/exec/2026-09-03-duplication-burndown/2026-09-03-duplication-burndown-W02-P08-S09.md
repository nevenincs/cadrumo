---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:dee902f6b0103f3fe995231382ed3476c1f70d1079175cc04e10ad9dcba6fd99'
step_id: 'S09'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Consolidate the lifecycle and operations clone component while preserving every command token, help key, policy, handler, and schema

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_lifecycle_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`
- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_app_ledger_lifecycle_command_specs.py src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py` -> `pass`

## Notes

49 literal parameter declarations were replaced (37 lifecycle, 12 operations) by an AST
rewrite that matches a call only when its keyword shape equals a primitive's exactly and
carries the identity fields across verbatim. A declaration differing by even one field is
left alone, so a divergent parameter cannot be absorbed into a shared contract.

Contract equivalence is proven by comparing the exported `LEDGER_LIFECYCLE_COMMAND_SPECS`
and `LEDGER_OPERATIONS_COMMAND_SPECS` before and after: 11 and 8 specs,
`sha256:d7c2e86c3577ce3cde1646e6123fd7724cfd0bc2d3a3cce481fa2fc1b283d65b` on both sides,
still identical after formatting. Every command token, help key, policy, handler,
parameter default and result schema is therefore unchanged.

The first comparison attempt reported a spurious divergence. `repr` on a dataclass holding
a frozenset is not stable across processes -- set iteration order follows the hash seed --
so the capability sets rendered in different orders. The comparison was redone through a
canonical serializer that sorts every set before rendering.

Clone count fell from 52 to 37; duplicated lines from 0.21% to 0.15%. Unused symbols fell
from 1420 to 1415: five of the six primitives are now consumed, and `_required_text_option`
remains unconsumed until the next migration Step.

The coverage gate went red immediately after the consolidation, correctly. Removing
lifecycle's literals left `evidence` and `inventory_analysis` -- which had each cloned
lifecycle -- now cloning each other, a file-set pairing the record did not carry. The
ledger was reconciled against the live scan through its owning generator, which is what
that record's contract requires; it is not a mute, and the detector's own count is
unchanged by it.

Two failures in the CLI test tree are pre-existing and were proven so by A/B against
copies of the unmodified modules: `test_root_command_specs` (root parameter tuple) and
`test_ledger_interface_contract_payloads` (a pydantic `extra_forbidden` payload) fail
identically with and without this change.
