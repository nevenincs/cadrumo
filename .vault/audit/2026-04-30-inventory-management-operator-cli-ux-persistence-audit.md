---
tags:
  - "#audit"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-29-inventory-management-research]]"
  - "[[2026-04-29-inventory-management-adr]]"
  - "[[2026-04-29-inventory-management-plan]]"
---

# Inventory Management Kent CLI UX Persistence Audit

Topic: Kent-facing CLI inventory/amortization UX and compliance hardening after WIP #216 was merged.

Audit surface: current `aeat profile assets`, `aeat profile inventory`, Anexo D ledger overlay, Path A JSON persistence, #216 governed persistence substrate, and legal calculation behavior for technical kit purchases spanning years and VAT rates.

Rewrite scope: vault audit artifact only; no runtime code changes.

## Executive Finding

The current v1 should not be treated as production-ready for Kent's real technical kit inventory.

It exposes useful CLI scaffolding for assets, amortization, and inventory ledgers, but the implementation is not yet aligned with the governed #216 persistence substrate, does not perform legally robust VAT/base decomposition or amortization validation, and presents Kent-facing UX failures that make real use risky.

UX score: **4.8/10**.

Decision gate: **hardening/reimplementation required before feature completion**.

## Manual Roleplay Evidence

Manual roleplay exercised Kent-style technical kit and retail inventory flows through the current CLI in an isolated temporary store.

Observed outcomes:

- Added `laptop-2024` to the temporary asset store.
- Added `nas-2025` to the temporary asset store.
- Added a FIFO `retail` inventory ledger with purchase movement.
- Recorded 2025 amortization values of `450.00` and `151.23`.
- Rejected an invalid date shape.
- Rejected an invalid asset class.
- Rejected an invalid decimal.
- Refused LIFO valuation.
- Reported a missing inventory ledger.
- Reported a missing asset.

The roleplay confirms the commands are discoverable enough to complete a narrow happy path, but also confirms that the CLI can report success in misleading cases and that the persistence/calculation substrate is not production-grade.

## Persona Audit Loops

### Kent UX Loop

Observed risks:

- Asset class input requires exact long enum strings, creating avoidable command friction.
- Trilingual support is shallow and does not yet make the workflows feel fully localized.
- Duplicate asset or ledger identifiers silently replace existing records.
- Repeated amortization recording no-ops while the CLI still says the entry was recorded.
- Error handling exists for malformed date, asset class, decimal, LIFO, missing ledger, and missing asset, but the workflow does not yet guide Kent toward correction.
- Technical kit purchases spanning years and VAT rates are not represented in a way Kent can confidently audit later.

UX score rationale: the CLI has a recognizable command surface and basic validation, but it is too easy to overwrite records, misread success messages, or enter legally ambiguous purchase data.

### Legal And Calculation Loop

Observed risks:

- VAT/base decomposition is missing.
- `useful_life_years` can bypass LIS table caps.
- `libertad` is modeled as a raw boolean without a governed calculation pathway.
- Cumulative amortization includes future entries.
- Inventory valuation method names are accepted labels, but computation is signed movement arithmetic rather than FIFO, PMP/coste medio, or layer-based valuation.
- LIFO refusal exists, but citation behavior shows drift and should be tightened.
- Legal anchors must stay explicit: LIS BOE-A-2014-12328, LIRPF BOE-A-2006-20764, RIRPF BOE-A-2007-6820.

### Persistence And Security Loop

Observed risks:

- `aeat profile assets` and `aeat profile inventory` write plaintext Path A JSON under `~/.config/aeat`.
- Writes use direct `write_text` behavior.
- The stores are not governed by Settings/root configuration.
- The stores bypass the #216 governed persistence substrate.
- #216 provides `SensitivityClass.FINANCIAL` ciphertext requirements, Envelope usage, AES-GCM encrypted envelopes, HKDF context, classification-bound AAD, locks, and rotation planning.
- Current asset and inventory ledgers bypass those controls despite containing financial records.

## Findings By Severity

### Critical

- Financial asset and inventory ledgers bypass #216 governed persistence and are stored as plaintext Path A JSON.
- Duplicate identifiers silently replace existing asset or ledger records.
- Repeated amortization recording can no-op while reporting success.
- Legal amortization behavior is not sufficiently constrained for Kent's real technical kit inventory.

### High

- VAT/base decomposition is missing, blocking correct treatment of purchases across VAT rates.
- Inventory valuation labels do not correspond to real FIFO/PMP/coste medio layer calculations.
- `useful_life_years` can bypass LIS table caps.
- Cumulative amortization includes future entries.
- Anexo D overlay only writes `0155` and `0173` when ledgers/assets are supplied; fallback caller values remain otherwise.

### Medium

- Asset class values require exact long enum strings.
- Trilingual UX is shallow.
- LIFO refusal exists but citation behavior should be corrected and anchored.
- Missing asset and missing ledger errors are detected but not yet part of a guided correction workflow.

## Decision Gate

Do not treat current v1 as production-ready for Kent's real technical kit inventory.

The feature requires hardening or reimplementation before completion, with priority on governed #216 persistence/security opt-in, legally grounded VAT/base and amortization behavior, real inventory valuation layers, and CLI UX that prevents silent data loss or misleading success states.
