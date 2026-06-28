---
tags:
  - "#audit"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-transaction-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `transaction-catalogue` Code Review

Follow-up local review on 2026-04-14 found and closed three branch defects before final sign-off:

- `TransactionCatalogue` did not implement the required iteration contract and instead inherited `BaseModel.__iter__`, yielding model field tuples rather than `Transaction` records.
- `link_invoice()` accepted whitespace-only identifiers and silently normalized them to `None`, turning a link operation into an implicit unlink.
- `set_classification()` / `link_invoice()` leaked raw `pydantic.ValidationError` exceptions through the public service and CLI surface instead of raising typed AEAT-domain errors.

After those fixes and their regression tests landed, no remaining LOW, MEDIUM, HIGH, or CRITICAL findings were identified across the reviewed change set.

## Reviewed Scope

- `src/aeat/domain/financial/transactions/__init__.py`
- `src/aeat/domain/financial/transactions/_enums.py`
- `src/aeat/domain/financial/transactions/_errors.py`
- `src/aeat/domain/financial/transactions/_models.py`
- `src/aeat/domain/financial/transactions/_service.py`
- `src/aeat/domain/financial/transactions/_stubs.py`
- `src/aeat/domain/financial/transactions/test_models.py`
- `src/aeat/domain/financial/transactions/test_catalogue.py`
- `src/aeat/domain/financial/transactions/test_cli.py`
- `src/aeat/entrypoints/cli/financial/txs.py`
- `src/aeat/entrypoints/cli/financial/__init__.py`
- `src/aeat/config.py`
- `env/.env.example`
- `src/aeat/domain/financial/providers/__init__.py`

## Checklist Outcome

- `transaction_id` is derived deterministically from the requested tuple using a canonical SHA-256 payload over the merged upstream fields `raw.transaction_id`, effective value date, amount, and narrative.
- `Transaction` preserves the wrapped `RawTransaction` verbatim and every catalogue update returns a new validated record instead of mutating `raw`.
- Invoice/category references remain runtime `str | None` fields, while `_stubs.py` contains typing-only Protocol placeholders and does not import unmerged sibling packages.
- All transaction models are strict frozen pydantic v2 models, and the closed sets use `enum.StrEnum`.
- Public callers import from `aeat.domain.financial.transactions` only; all implementation modules remain underscored and are not re-exported directly.
- Logging uses `aeat.core.logging.get_logger(__name__)`, and the transaction-specific errors inherit from `aeat.core.errors.AeatError`.
- `just lint`, `just typecheck`, `just test`, and `just hooks` all passed locally on this branch.

## Residual Risks

- The default CLI workflow currently targets one configured catalogue file named `transactions.json` under `AEAT_FINANCIAL_TXS_DIR`. Multi-catalogue selection, ingestion-to-catalogue population, and downstream invoice/category integration remain future work by design.
