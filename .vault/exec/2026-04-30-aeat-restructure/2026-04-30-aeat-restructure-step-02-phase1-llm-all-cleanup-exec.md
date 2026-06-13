---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-02-phase1-filing-utc-now-exec]]"
---

# 2026-04-30-aeat-restructure step-02 phase-1 llm __all__ cleanup

## status

Step 2 PR 4 of 5 (batched: items 4 + 5 from the original 6-item list since both touch `aeat/adapters/outbound/llm/__init__.py` `__all__` and would conflict if shipped as separate parallel PRs). `__all__` removals of `_FakeAdapter` + `ProviderRequest` per ADR Dead-code workstream / Phase 1.

## scope

- Remove `"_FakeAdapter"` from `src/aeat/adapters/outbound/llm/__init__.py` `__all__`.
- Remove `"ProviderRequest"` from `src/aeat/adapters/outbound/llm/__init__.py` `__all__`.
- Keep the `from ._providers import ProviderRequest, _FakeAdapter` line — both symbols remain accessible via the private path `aeat.adapters.outbound.llm._FakeAdapter` / `aeat.adapters.outbound.llm.ProviderRequest` for tests that use them.

## pre-merge safety check

`grep -rn "_FakeAdapter|ProviderRequest" --include="*.py" .`: hits are confined to `aeat/adapters/outbound/llm/_providers/*` (internal) and `aeat/adapters/outbound/llm/_client.py` (internal). No external consumers reference either symbol.

## verification

```
import aeat.adapters.outbound.llm
assert '_FakeAdapter' not in aeat.adapters.outbound.llm.__all__
assert 'ProviderRequest' not in aeat.adapters.outbound.llm.__all__
from aeat.adapters.outbound.llm import _FakeAdapter, ProviderRequest  # private path still works
```

All assertions pass.

## next step

Step 2 PR 5 — `schema._extractor.py` whole-file deletion (final Phase-1 item).
