---
tags:
  - '#adr'
  - '#iva-rate-import-cycle-resolution'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
  - "[[2026-06-01-output-language-typed-constant-migration-adr]]"
  - '[[2026-06-04-iva-rate-import-cycle-resolution-research]]'
---


# `iva-rate-import-cycle-resolution` adr: lazy-build dicts to break iva↔invoices cycle | (**status:** `accepted`)

## Authoring note

Authored via the Write tool — same bash-quoting constraint as the M303 dual-keying, RegistryPeriodCode, and OutputLanguage ADRs landed on 2026-06-01. Commit-bot validates via `vault check all`.

## Problem statement

P05.S14 of the suite-redgreen plan. Two facts collide:

1. `aeat.domain.iva._invoice_classification` builds two dict literals keyed by `IvaRate` at module-import time. Today it imports `from ..invoices._enums import IvaRate`, which bypasses the sibling-package init.

2. `aeat.diagnostics.test_identity_primitive_placement::test_no_sibling_domain_enum_imports` rejects sibling-domain `_enums` imports as a structural-hygiene violation.

The naive fix (`from ..invoices import IvaRate`) creates a real circular init: `invoices/__init__.py` re-exports symbols whose modules import from `iva._invoice_classification` (via the recargo-equivalencia path), which would re-enter `invoices` mid-init.

## Decision: Path (c) — lazy-build dicts via `@lru_cache` helper

Defer dict construction from module-import time to first-call time, and route the runtime `IvaRate` lookup through `from ..invoices import IvaRate` inside the helper body. The package init has finished by the time any caller hits the helper, so the cycle never closes.

Concrete shape (per PM's sketch):

```python
from typing import TYPE_CHECKING
from functools import lru_cache

if TYPE_CHECKING:
    from ..invoices._enums import IvaRate  # type-checker only; no runtime import

@lru_cache(maxsize=1)
def _iva_rate_to_iva_kind() -> dict["IvaRate", IvaRateKind]:
    from ..invoices import IvaRate  # runtime lazy: invoices fully loaded
    return {IvaRate.RATE_0: IvaRateKind.ZERO, ...}
```

Every existing module-level dict reference becomes a `_iva_rate_to_iva_kind()` call.

## Why not Path (a) — move IvaRate to `domain/iva/_rate.py`

Semantically defensible (IvaRate IS an iva-domain concept), but two costs make it heavier than (c):

- `domain.invoices` is the public surface for invoice-shaped types (already exports IvaRate via its package init). Moving the source breaks every external consumer that imports from `aeat.domain.invoices`.
- The re-export shim in `_enums` would then violate the same sibling-domain-`_enums` rule that surfaced this issue. The cycle moves rather than resolves.

## Why not Path (b) — move IvaRate to `core/iva_rate.py`

`core/` is the cross-domain spine reserved for closed-value primitives consumed by multiple domains as type-system axes (per `core-struct-docstring-links` rule). IvaRate IS consumed across iva + invoices + adapters + cli — promotion to core IS architecturally defensible long-term. But:

- 15 consumer files would need import path updates.
- The `core/` directory is curated; adding a new module there warrants its own placement justification.
- The same cycle gets re-resolved by import-path change without an architectural decision about IvaRate's home domain.

Path (b) is a future-hardening direction, not the lowest-blast-radius fix.

## Trade-offs accepted

- One-time per-call cost on first invocation (negligible after lru_cache hit).
- The `TYPE_CHECKING` guard preserves static-type-checker fidelity; mypy / pyright see `dict[IvaRate, IvaRateKind]` correctly.
- The runtime lazy import is the documented exit from circular-init hell per Python's standard pattern; not novel.

## Consequences

- `_invoice_classification.py` changes: ~20 LOC (helper + call-site updates).
- 0 external API changes. Public surface of `aeat.domain.iva` and `aeat.domain.invoices` unchanged.
- `test_no_sibling_domain_enum_imports` passes because the module-level import drops; the runtime import is from the package (`..invoices`), not the sibling `_enums`.
- Future-hardening direction (Path b promotion to core) stays open and can be revisited if IvaRate consumers grow significantly.

## Dispatch

Implementation handed to coder1-2 or coder2-2 (per PM availability). Single-file ~20 LOC change. Estimated 1 commit.
