---
tags:
  - "#exec"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `transaction-catalogue` `phase-1` `step-1`

Established the transaction package surface, immutable models, typed errors, sibling-safe Protocol stubs, and the additive configuration/export changes needed to wire the new catalogue into the repo.

- Modified: `src/aeat/config.py`
- Modified: `src/aeat/domain/financial/providers/__init__.py`
- Modified: `src/aeat/entrypoints/cli/financial/__init__.py`
- Created: `src/aeat/domain/financial/transactions/__init__.py`
- Created: `src/aeat/domain/financial/transactions/_enums.py`
- Created: `src/aeat/domain/financial/transactions/_errors.py`
- Created: `src/aeat/domain/financial/transactions/_models.py`
- Created: `src/aeat/domain/financial/transactions/_service.py`
- Created: `src/aeat/domain/financial/transactions/_stubs.py`
- Modified: `env/.env.example`

## Description

Implemented the new `aeat.domain.financial.transactions` public surface with strict frozen pydantic v2 models and `StrEnum` classifications. `Transaction` now derives and enforces its stable SHA-256 ID from the wrapped `RawTransaction`, while `TransactionCatalogue` freezes its internal mapping and validates key-to-record consistency. The settings layer gained `aeat_financial_txs_dir`, and `aeat.domain.financial.providers` now re-exports `RawTransaction` so downstream packages can depend on the provider public API exactly as requested.

## Tests

Model and service behaviour were verified first through the colocated transaction-package tests before the broader repo-wide gates were run in step 2.
