---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-7

## scope

Plan row A7: fix the `__all__` private-name leak and verify the
`InventoryValuationJson` double-registration claim.

## changes

`src/aeat/adapters/outbound/llm/_providers/__init__.py`: removed
`_DeterministicAdapter` and `_ProviderAdapter` from `__all__`. The
private symbols remain importable for internal callers, but
`from aeat.adapters.outbound.llm._providers import *` no longer
re-exports the underscore-prefixed names.

`InventoryValuationJson` double-registration: investigated and
disproved. A runtime walk after `import
aeat.entrypoints.cli.data.ledgers.inventory` confirms `SCHEMA_REGISTRY`
contains exactly one entry mapping
`"data ledgers inventory valuation preview"` to
`InventoryValuationJson`, alongside one each for the list / mutation
classes. The audit's claim was stale.

## verification

`python -c "from aeat.adapters.outbound.llm._providers import __all__;
assert all(not n.startswith('_') for n in __all__)"` exits cleanly
with `__all__ == ['AnthropicAdapter', 'GeminiAdapter',
'LocalAdapter', 'OpenAIAdapter', 'ProviderCompletion',
'ProviderRequest']`.

`pytest src/aeat/adapters/outbound/llm/
src/aeat/entrypoints/cli/data/ledgers/` returns 34 passed.

Runtime walk of `SCHEMA_REGISTRY` reports `InventoryValuationJson`
once.
