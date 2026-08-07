---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ffe86b64055d6c69460a4bddb4d8083078ce51f8d90af8a10c8c4a69dd6efbf2'
step_id: 'S25'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S25

## Outcome

Swept the IVA category and clave surfaces by meaning. **Fragmented authority named: the clave-to-category correspondence is expressed in three places, in two directions, with no shared source.**

The Step framed subjection and operation-type as separate axes and asked whether a third encoding of either exists. It does — not as a third copy of one axis, but as a third encoding of the *bridge between* them.

## The three sites

| Site | Direction | Coverage |
|---|---|---|
| `entrypoints/cli/_ledger_business_invoice_cli.py:81` `_OPERATION_TYPE_TO_IVA_CATEGORY` | clave -> category | `E A T S I` |
| `application/invoices/_source_resolver.py:121` `_CLAVE_BY_KIND_AND_CATEGORY` | (kind, category) -> clave | `E S I A` — **no T** |
| `application/invoices/_source_resolver.py:623` | category -> clave, special case | `T` only |

The second and third are the same lookup: the reverse table is incomplete by construction, and the one entry missing from it is patched by a hand-written `if` sitting two lines above it.

## Is a wrong figure reachable today

**No, and the reason is worth recording rather than assuming.** The CLI persists `operation_type=parsed_operation_type` alongside the derived category (`_ledger_business_invoice_cli.py:424`), and `_intracommunity_clave` consults an explicit `operation_type` FIRST and returns without reading `iva_category`. So a CLI-created triangulation invoice resolves its clave from the stored operation type and never reaches the reverse table.

The category-only fallback path is reachable — an operator may supply `--iva-category` without `--operation-type` — and triangulation IS handled there, by the special case at `:623`. Every one of the five claves resolves. The three encodings currently agree.

## Why it is still a finding

The correspondence has no single source, and the coverage gap is real even though it is currently patched: the reverse table would silently return `None` for triangulation, and `None` means the operation produces no M349 clave. Nothing prevents a sixth clave being added to the forward table and the reverse table alone, leaving the special case as the only hint that the two were ever meant to be inverses.

Not actioned here. Both `_source_resolver.py` sites sit inside the invoice campaign's working set, and `W04.P06.S15` already owns a clave-mapping fix on the neighbouring `domain/iva/_classification.py` R13 surface. This belongs as a Step there, not as a foreign edit mid-flight.
