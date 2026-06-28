---
tags:
  - "#plan"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-inventory-management-cli-design-research]]"
  - "[[2026-04-30-inventory-management-cli-design-adr]]"
  - "[[2026-04-30-inventory-management-cli-design-reference]]"
  - "[[2026-04-30-inventory-management-hardening-plan]]"
---

# inventory-management cli design plan: data ledgers rewrite

## Objective

Rewrite the inventory and amortization CLI design around the future canonical `aeat data ledgers ...` surface and harden the feature for Kent-facing use.

The current `aeat profile assets` and `aeat profile inventory` commands are prototype-compatible only. They may remain temporarily, but they should not become public forwarding commands after the canonical surface exists.

## Command tree

Design and implement the canonical `aeat data ledgers ...` command family.

Target command groups:

```text
aeat data ledgers assets ...
aeat data ledgers assets amortization ...
aeat data ledgers inventory ...
aeat data ledgers inventory movement ...
aeat data ledgers inventory valuation ...
aeat data ledgers anexo-d ...
aeat data ledgers migrate ...
aeat data ledgers doctor ...
```

Use stage-oriented workflows. Commands that calculate, mutate, migrate, replace, or overlay filing values should expose preview/apply semantics.

Label all future syntax examples as future syntax until implemented.

Keep current profile commands out of future canonical documentation except as current prototype-compatible commands while the replacement is being built.

Remove the old public profile ledger paths after canonical commands exist. Do not add moved or deprecated forwarding aliases.

## Persistence and migration

Move financial ledgers from plaintext Path A JSON under `~/.config/aeat` to governed encrypted storage from #216.

Store asset, amortization, inventory, movement, valuation, and migration records as `SensitivityClass.FINANCIAL`.

Use envelope-backed encrypted persistence, classification-bound authenticated data, lock-aware writes, schema versions, and auditable migration results.

Add plaintext detection before normal ledger operations. If plaintext stores exist, commands should report the condition and guide the user to migration rather than silently reading and rewriting unsafe data.

Migration preview should list detected stores, target records, duplicate conflicts, unsupported records, and rollback constraints.

Migration apply should be idempotent, auditable, and protective against duplicate IDs.

## VAT and basis models

Replace ambiguous purchase amount handling with explicit monetary decomposition.

Model gross amount, VAT rate, VAT amount, deductible VAT, non-deductible VAT, amortizable base, currency, purchase date, supplier reference where available, and activity allocation.

Support VAT rates `0`, `4`, `10`, and `21`.

Validate gross/net/VAT consistency. Refuse inconsistent values with registered errors and clear correction guidance.

Make technical kit purchases across different years and VAT rates easy to inspect.

Ensure amortization uses amortizable base rather than ambiguous purchase cost.

## Amortization engine

Preserve the casilla mapping: `0173` is fixed-asset amortization.

Validate useful-life inputs against supported table constraints or a governed exception model. Do not allow `useful_life_years` to bypass table caps silently.

Replace raw `libertad` boolean behavior with a governed rule path that records the legal basis, eligibility, calculation method, and trace output.

Exclude future amortization entries from prior-year cumulative totals.

Make repeated amortization recording truthful. A no-op should report unchanged or already recorded, not recorded.

Expose calculation traces showing base, rate, period, cumulative amount, remaining basis, activity allocation, and source records.

## Inventory valuation engine

Preserve the casilla mapping: `0155` is inventory or stock variation.

Replace signed movement arithmetic with true valuation layers.

Implement FIFO layers with movement date, quantity, unit cost, remaining quantity, and depletion trace.

Implement PMP or coste medio behavior with weighted-average recalculation after purchases and traceable cost basis.

Keep LIFO refused. The refusal must use a registered error and clear legal anchoring.

Define returns, corrections, negative stock handling, duplicate movement IDs, and unsupported movement shapes.

Ensure ledger summaries reconcile quantities, valuation totals, stock variation, and Anexo D overlay values.

## Output, errors, and i18n

Register hardened commands in the shared JSON schema catalogue before claiming JSON support.

Every advertised JSON command should emit the shared success envelope on stdout and use the shared error envelope on stderr.

Add schema tests for each JSON-producing command.

Route invalid date, invalid decimal, invalid asset class, duplicate ID, missing asset, missing ledger, LIFO, negative stock, plaintext detection, unsupported target, and unsupported JSON through registered errors.

Use stable categories, exit codes, stderr prefixes, and copy-paste-ready suggestions.

Prepare Kent-facing messages for trilingual output in Spanish, English, and Hungarian.

Keep human terminal copy ASCII-safe. Do not depend on Unicode symbols for meaning.

Design command output so future profile banners can display active profile, tax identity, actividad, period, and storage state without rewriting the workflow.

## Scenario tests

Build real-behavior tests rather than tautological tests.

Cover the scenario matrix:

- VAT rates `0`, `4`, `10`, and `21`
- Multi-year purchases
- Shared assets
- Multiple actividades
- Returns
- Corrections
- Invalid input
- LIFO refusal
- Negative stock
- Duplicate IDs
- Plaintext detection
- JSON automation

Add technical kit scenarios for assets such as a laptop and NAS across different years and VAT rates.

Add retail inventory scenarios that prove FIFO layer depletion and PMP weighted-average behavior.

Add Anexo D overlay scenarios proving `0155` and `0173` are generated only from validated ledger data and that fallback caller values remain distinguishable when no ledger overlay is available.

Add migration scenarios that start from real plaintext Path A JSON stores and end in governed encrypted storage without relying on mocks, stubs, skips, xfail, or monkeypatch shortcuts.

## Documentation and transition

Update documentation only after the canonical command tree and tested behavior exist.

Document current profile commands as current prototype-compatible behavior, not future canonical UX.

Document `aeat data ledgers ...` as future syntax until implemented, then as canonical syntax after tests pass.

Document migration from plaintext Path A JSON to governed encrypted storage.

Document which values are source-of-truth when ledgers are supplied and when caller-provided Anexo D values remain in effect.

Document that JSON support is bounded to registered and tested commands.

Document the removal of the old public profile ledger paths after the canonical surface exists.

## Completion gate

The rewrite is complete only when the canonical `aeat data ledgers ...` surface exists, financial ledgers use governed encrypted storage, plaintext migration is handled, VAT/base decomposition is explicit, amortization is legally constrained and traceable, FIFO and PMP labels reflect true valuation layers, errors and JSON output use shared contracts, trilingual Kent-facing messages are in place for the hardened path, and the scenario matrix passes through real-behavior tests.
