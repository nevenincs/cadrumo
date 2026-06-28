---
tags:
  - "#research"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-29-inventory-management-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-04-25-error-code-registry-adr]]"
---

# inventory-management cli design research: corrected ledger command surface

## Purpose

This research records the corrected CLI design for inventory and amortization ledgers after the Kent UX and persistence audit found that the current v1 surface is prototype-compatible only.

The current command surface is `aeat profile assets` and `aeat profile inventory`. Those commands are useful as scaffolding and compatibility evidence, but they are not the future canonical Kent-facing UX.

The future hardened canonical surface is `aeat data ledgers ...` after implementation. Current profile groups should not become public forwarding commands after the canonical surface exists.

## Evidence summary

The existing inventory research established the legal and calculation boundary for Anexo D normal overlays. Casilla `0155` is inventory or stock variation. Casilla `0173` is fixed-asset amortization. They must not be inverted. Ledgers may derive those values, but direct caller-supplied aggregate values must remain available when no governed ledger overlay exists.

The Kent CLI UX and persistence audit found that the current v1 commands can complete narrow happy paths but are not production-ready. They store financial ledgers as plaintext Path A JSON under `~/.config/aeat`, allow silent replacement of duplicate identifiers, can report success for no-op amortization recording, and do not yet model VAT/base decomposition or real inventory valuation layers.

The CLI wireframe decision establishes a Kent-first command language. Kent-facing work belongs under stable operator domains. `data` is the domain for importing, classifying, editing, and preparing financial evidence. Inventory and amortization ledgers are financial evidence and should be presented there rather than as profile setup.

The CLI wireframe reference also establishes the hardening norms that apply to this feature: local-only operation, preview/apply workflows, no silent overwrite, registered errors, JSON envelopes for registered commands, trilingual messages, profile banners as a future requirement, and ASCII-safe terminal copy.

The JSON output contract ADR provides the future automation contract. Current JSON support in the inventory prototype is bounded. Future ledger commands must register and test the shared JSON envelope before documentation claims JSON support.

The error-code registry ADR provides the error vocabulary. Future ledger commands must route domain failures through registered errors rather than ad hoc Typer or Click failures.

## Current behavior

Current commands live under `aeat profile assets` and `aeat profile inventory`.

They are prototype-compatible and can prove local workflows such as adding technical kit assets, adding inventory ledgers, rejecting malformed dates, rejecting invalid decimals, rejecting invalid asset classes, refusing LIFO, and reporting missing assets or ledgers.

They should not be described as the canonical UX. They are current implementation scaffolding and should leave the public Kent-facing CLI once the future canonical surface exists.

Current persistence is plaintext Path A JSON under `~/.config/aeat`. This is not acceptable for production financial ledgers. The target is encrypted governed storage from #216 using `SensitivityClass.FINANCIAL`, envelope encryption, migration from plaintext stores, lock-aware writes, and detection of existing plaintext data.

Current inventory valuation labels are not real FIFO or PMP layers. The current model uses signed movement arithmetic and explicit closing stock values. The target is true valuation layers with quantities, unit costs, remaining layer quantities, dates, and method-specific depletion or weighted-average behavior.

## Corrected canonical command direction

The future hardened command family should be rooted under `aeat data ledgers ...`.

Future syntax examples:

```text
aeat data ledgers assets add ...
aeat data ledgers assets show ...
aeat data ledgers assets amortization preview ...
aeat data ledgers assets amortization apply ...
aeat data ledgers inventory create ...
aeat data ledgers inventory movement add ...
aeat data ledgers inventory valuation preview ...
aeat data ledgers inventory valuation apply ...
aeat data ledgers anexo-d preview --modelo 100 --year 2025
aeat data ledgers anexo-d apply --modelo 100 --year 2025
```

These examples are future syntax, not current shipped commands.

The current profile commands should not remain as public forwarding commands once the canonical surface exists. Until then, documentation must state that `aeat profile assets` and `aeat profile inventory` are current prototype-compatible commands, not the final command language.

## Legal and calculation findings

Casilla `0155` is inventory or stock variation. Casilla `0173` is fixed-asset amortization.

VAT/base decomposition is missing today. The hardened design must separately model gross amount, VAT rate, VAT amount, deductible VAT treatment, non-deductible VAT treatment, and amortizable base.

`useful_life_years` can currently bypass legal table caps. The hardened design must validate useful-life overrides against supported table constraints or require a governed exception path.

`libertad` is currently a raw boolean. The hardened design needs a governed calculation pathway with explicit trace output and legal basis handling.

Future amortization entries currently affect prior-year cumulative totals. The hardened design must filter cumulative amortization by filing year.

Inventory valuation labels currently do not represent true FIFO or PMP layer behavior. The hardened design must implement true valuation layers before using those labels as calculation claims.

LIFO must remain refused. The refusal should use the shared error registry and retain clear legal anchoring.

## CLI design findings

The ledger UX should be stage-oriented. Mutating workflows should distinguish preview from apply and must not silently overwrite existing records.

All writes must reject duplicate IDs unless the user supplies explicit replacement intent. Replacement and migration must be auditable.

Human output must be ASCII-safe. Commands should produce clear state words such as created, updated, unchanged, migrated, refused, and blocked.

Trilingual messages are required for Kent-facing command output and errors. The implementation can land language coverage incrementally, but command behavior should be structured so localization is not an afterthought.

Profile banners are a future requirement. Ledger commands should be designed so they can display the active profile, tax identity, activity, period, and storage state once the profile banner contract exists.

JSON output must not be claimed until each command is registered in the shared schema catalogue and tested against the shared success envelope. Error JSON must follow the registry envelope on stderr.

## Scenario matrix

The hardened command design must cover VAT rates `0`, `4`, `10`, and `21`.

It must cover multi-year purchases, shared assets, multiple actividades, returns, corrections, invalid input, LIFO refusal, negative stock, duplicate IDs, plaintext detection, and JSON automation.

It must cover technical kit examples across years and VAT treatments, including asset purchases with amortization traces and retail inventory with true valuation layers.

It must cover preview/apply boundaries for asset creation, inventory movement recording, valuation calculation, Anexo D overlay generation, plaintext migration, and duplicate replacement.

## Research conclusion

The corrected design should treat the current profile commands as temporary implementation scaffolding and move the canonical hardened UX to `aeat data ledgers ...` without keeping old public command paths.

The rewrite must be broad enough to address command tree shape, governed encrypted persistence, VAT/base models, legal amortization constraints, real inventory valuation layers, output/error/i18n contracts, scenario tests, migration behavior, and documentation truthfulness.
