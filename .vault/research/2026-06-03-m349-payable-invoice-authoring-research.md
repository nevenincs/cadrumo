---
tags:
  - '#research'
  - '#m349-payable-invoice-authoring'
date: '2026-06-03'
modified: '2026-06-29'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-06-03-m349-legal-grounding-debt-research]]"
---

# `m349-payable-invoice-authoring` research: M349 payable mirror authoring - closed

## Current State - 2026-06-29

The original payable-authoring gap is closed in the current registry.

Executable registry inventory over Modelo 349 `2020-y-siguientes` reports:

- invoice bindings: 34 total;
- `collectible_invoice` bindings: 17;
- `payable_invoice` bindings: 17;
- missing substantive M349 legal refs across invoice bindings: 0.

The current implementation is not the original draft plan:

- Collectible bindings remain in
  `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`.
- Payable mirror bindings live in the dedicated fragment
  `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0008-payable-bindings.toml`.
- Payable mirrors use `claves = ["A", "I", "T"]`, covering received
  acquisitions, intra-community services, and triangular-operation rows.
- The public declarante summary casillas keep their existing binding ids. The
  invoice source resolver folds the payable mirror results into those public
  ids after resolving each direction under its typed source kind, rather than
  adding formula wrappers for the declarante casillas.

Do not carry forward the historical `ley-37-1992:art-141` recommendation. The
bundled consolidated LIVA text identifies article 141 as the travel-agency
special regime, not M349 triangulation. The current M349 triangulation
grounding uses `ley-37-1992:art-26` and `rd-1624-1992:art-79`.

## Historical Finding

The 2026-06-03 audit found that M349 declared only 17
`collectible_invoice` bindings and no `payable_invoice` bindings. That meant
received intracommunity acquisitions could be rejected at the source-kind gate
before their clave values were considered.

That historical state is no longer current.

## Current Verification

The current registry tests pin the closed state in
`src/aeat/domain/calculations/registry/tests/test_modelo_349_registry.py`:

- `test_committed_modelo_349_invoice_bindings_resolve_substantive_legal_refs`
  asserts 34 invoice bindings, split 17 collectible and 17 payable, with all
  substantive legal refs resolved and no `ley-37-1992:art-141`.
- `test_committed_modelo_349_construct_includes_invoice_bindings` asserts the
  construct includes the current invoice binding set.
- The scalar and row binding tests assert the payable mirror ids and the
  collectible/payable row binding cohorts.

Focused verification run:

```
uv run pytest src\aeat\domain\calculations\registry\tests\test_modelo_349_registry.py::test_committed_modelo_349_invoice_bindings_resolve_substantive_legal_refs src\aeat\domain\calculations\registry\tests\test_modelo_349_registry.py::test_committed_modelo_349_construct_includes_invoice_bindings -q
```

Result: 2 passed.

## Current Binding Shape

The current payable mirror ids add `-adquisicion` to the corresponding public
binding concepts:

- `iva-349-declarante-numero-operadores-adquisicion`
- `iva-349-declarante-importe-operaciones-adquisicion`
- `iva-349-declarante-numero-rectificaciones-adquisicion`
- `iva-349-declarante-importe-rectificaciones-adquisicion`
- `iva-349-operador-row-codigo-pais-adquisicion`
- `iva-349-operador-row-nif-adquisicion`
- `iva-349-operador-row-apellidos-adquisicion`
- `iva-349-operador-row-clave-adquisicion`
- `iva-349-operador-row-base-adquisicion`
- `iva-349-rectificacion-row-codigo-pais-adquisicion`
- `iva-349-rectificacion-row-nif-adquisicion`
- `iva-349-rectificacion-row-apellidos-adquisicion`
- `iva-349-rectificacion-row-clave-adquisicion`
- `iva-349-rectificacion-row-ejercicio-adquisicion`
- `iva-349-rectificacion-row-periodo-adquisicion`
- `iva-349-rectificacion-row-base-rectificada-adquisicion`
- `iva-349-rectificacion-row-base-anterior-adquisicion`

These entries mirror the existing collectible record structure while using the
`payable_invoice` source kind.
