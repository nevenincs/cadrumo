---
tags:
  - '#research'
  - '#m349-payable-invoice-authoring'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `m349-payable-invoice-authoring` research: `M349 R21 closure: mirror payable_invoice bindings + decl casilla union`

Subagent ground-truth pass for the apex R21 partial-closure gap:
the 2026-06-03 audit confirmed M349's registry declares 17/17
bindings as `source = "collectible_invoice"` (entregas / output
side) and ZERO `payable_invoice` (adquisiciones / input side).

## Root cause

`InvoiceCatalogueSourceResolver._invoice_sources_for_revision`
(`_source_resolver.py:76`) computes the active source set from
DECLARED bindings. No binding declares `payable_invoice`, so the
resolver's `active_sources` set never includes it, so received
intracomunitarias (`InvoiceKind.RECEIVED` + clave "A") are
filtered out at the source-kind gate — even though every existing
binding's `claves` list includes "A". The clave filter is moot
when the source filter rejects them upstream.

The casilla layer has no separate adquisiciones casillas. The four
declarante aggregates (`decl.numero-operadores`,
`decl.importe-operaciones`, `decl.numero-rectificaciones`,
`decl.importe-rectificaciones`) plus the per-operador and
per-rectificacion row producers are **clave-discriminated within
one record stream**, not clave-segregated casillas.

## What the resolver needs (zero changes)

- `_OWNED_SOURCES` (line 25) already includes `"payable_invoice"`.
- `_invoice_sources_for_revision` (line 76) auto-discovers the
  active set from declared bindings — adding payable bindings
  turns it on.
- `_invoice_source_kind` (line 107) already maps
  `InvoiceKind.RECEIVED → "payable_invoice"`.
- `_intracommunity_clave` (lines 126-136) already returns "A" for
  received reverse-charge intracomunitarias.

The `_InvoiceSelector` model at `_bindings.py` is source-agnostic
(validates `selector.fact`, `claves`, `rectification_scope`,
`grouping`, `record`, `row_field` — none of which encode
direction). `INVOICE_BINDING_SOURCE_KINDS` (line 31) already
enumerates `payable_invoice`. The selector layer needs zero
changes.

**The entire gap is registry-authoring + casilla/formula
adjustment.**

## Authoring plan

### Phase 1 — mirror payable bindings (17 new entries)

Append 17 mirror entries to
`src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`
(no new file). Each new binding `id` should suffix `-adquisicion`
(e.g., `iva-349-declarante-numero-operadores-adquisicion`). Each
new binding:

- Carries the same `selector` shape (fact / row_field / grouping
  / record / rectification_scope) as its collectible counterpart.
- Sets `source = "payable_invoice"`.
- Narrows `claves` to the acquisitions subset: `["A"]` for pure
  adquisiciones, `["T"]` for triangulación-as-intermediario where
  direction matters (decide per binding's semantic — the four
  declarante aggregates may need the broader `["A", "T"]`).
- Same `aggregation`.
- Substantive legal_refs ADDED (currently the E-side bindings
  carry only procedural refs; the same pass should close that
  authoring debt):
  - `ley-37-1992:art-15` (definición adquisición intracomunitaria)
  - `ley-37-1992:art-26` (adquisiciones intracomunitarias exentas
    — A side; do NOT add `art-25` which is E-side)
  - `ley-37-1992:art-141` (régimen triangulación — for T-bearing
    bindings)

### Phase 2 — declarante casilla union

The four `decl.*` casillas each declare a single `binding = "..."`
scalar. The current schema does not support binding-list-per-casilla.
Resolution path: introduce a registry-level `sum` formula over
both binding ids (collectible + payable), replacing the single
`input_kind = "bound"` on each `decl.*` casilla. The formula
authoring lands at
`src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/formulas/`.

### Phase 3 — registry test gates

Pin the new behaviour with two test surfaces:

- A registry-level conformance test asserting M349 has both
  collectible and payable bindings for each declarante aggregate.
- A real-backend integration test that seeds the bucket with both
  ISSUED and RECEIVED intracomunitarias and asserts the
  declarante aggregates sum across both directions.

## Authoring atomicity

The 17 mirror bindings + 4 formula updates land in one atomic
explicit-path commit per the relocation-atomicity rule (single
M349 revision; coordinated registry mutation; downstream resolver
behaviour shifts at the same instant). Splitting bindings from
formulas would leave a window where the payable bindings exist
but the casillas still read only the collectible binding, and the
aggregate output is silently halved.

## Source

Subagent ground-truth pass 2026-06-03 against apex R21 partial
closure. Cited file:line evidence:
- `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`
- `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/casillas/0001-casillas.toml`
- `src/aeat/domain/calculations/registry/_bindings.py:31`
  (`INVOICE_BINDING_SOURCE_KINDS`)
- `src/aeat/application/invoices/_source_resolver.py:25,76,107,126`
- M349 is currently the only modelo project-wide with
  invoice-source bindings — no M303/M390 prior art for the mirror
  pattern; the M349 collectible patterns are the authoritative
  template.
