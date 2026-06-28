---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S175
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S175 — centralise `DEFAULT_CURRENCY` constant

## Outcome

`DEFAULT_CURRENCY: Final[str] = "EUR"` introduced in
`src/aeat/core/external_constants.py`. 17 production-default sites across
10 files migrated to read from the constant.

## Sites enrolled (migrated)

| File | Line | Pattern |
|------|------|---------|
| `application/ledger/_models.py` | 48 | `Field(default=DEFAULT_CURRENCY, ...)` |
| `application/ledger/_business_operation_invoice.py` | 166 | `Field(default=DEFAULT_CURRENCY, ...)` |
| `application/ledger/_business_operation_invoice.py` | 360 | `currency: str = DEFAULT_CURRENCY` (kwarg) |
| `application/ledger/_actions.py` | 300 | `if raw.currency == DEFAULT_CURRENCY` |
| `application/ledger/_preflight.py` | 180 | `if transaction.raw.currency != DEFAULT_CURRENCY` |
| `domain/transactions/_models.py` | 938 | `if self.raw.currency == DEFAULT_CURRENCY` |
| `domain/renta/_ledger_expenses.py` | 114 | `Literal["EUR"] = DEFAULT_CURRENCY` (×2) |
| `application/invoices/_importing.py` | 49 | `payload.setdefault("currency", DEFAULT_CURRENCY)` |
| `entrypoints/cli/_ledger.py` | 327 | `typer.Option(DEFAULT_CURRENCY, ...)` (×3) |
| `domain/currency/_service.py` | 34 | `if amount.currency == DEFAULT_CURRENCY` |
| `domain/calculations/registry/_bindings.py` | 2321 | `Field(default=DEFAULT_CURRENCY, ...)` |
| `application/calculations/_row_set_assembly.py` | 345 | `_coerce_text(..., default=DEFAULT_CURRENCY) or DEFAULT_CURRENCY` |
| `application/aggregation/_currency_predicates.py` | 35 | `!= DEFAULT_CURRENCY` |
| `core/config.py` | 347 | `Field(default=DEFAULT_CURRENCY, ...)` |

## Sites deferred (with reasoning)

- **Test fixture literals** (~50 occurrences in test_*.py files): fixture data
  for domain models, not config defaults. Migrating would add a production
  import to test modules and create circular-ish test concerns.
- **`domain/renta/_ledger_expenses.py` `Literal["EUR"]` type annotations**: the
  `Literal["EUR"]` is a type-system constraint; cannot be replaced by a
  `str` variable without losing the type narrowing.
- **`adapters/inbound/financial/providers/_pdf_n26.py:286,287`**: "EUR" appears
  in actual N26 PDF text being parsed; these are wire-format detection strings,
  not defaults.

## Collision check

`git diff -- <all target files>` before any edit returned empty output.
No non-authored WIP detected.

## Review gates (G1–G6)

All pass. No naked env reads; `Final[str]` typed; no user-facing strings
changed; no locale edits; no shims introduced; no tautological tests.

## Commit

`99e2b8070` — `core(external_constants): centralise DEFAULT_CURRENCY constant (S175/S176)`
