---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:efa2b4985c68a483f54ba9d61a0127eb6b0ebb5f3a44b9c732b30e3e5fb40d1b'
step_id: 'S166'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# replace bare closing-stock authority with a provenance-bearing physical-closing observation and prior-closing continuity contract

## Scope

- `src/cadrumo/domain/contribuyente/inventory`

## Description

- Replace bare ledger closing authority with immutable, evidenced physical-closing observations.
- Bind authority decisions, prior-year continuity, conflicts, and resolutions through canonical tamper-sensitive fingerprints.
- Enforce activity, year, date, cents, valuation-basis, evidence-role, temporal-causality, and selected-value invariants.
- Retain competing physical observations and conflict diagnostics regardless of the selected authority.
- Remove premature projection composition so S168 remains the sole projection owner.
- Hard-cut the domain `closing_stock` field without compatibility defaults.
- Add mutation, substitution, forgery, continuity, and provenance-retention tests.
- Amend the persisted ledger schema to version 3 with a required nullable, ledger-owned authority record.
- Revalidate the persisted decision, observation, and continuity bundle through the canonical resolver on every load.

## Outcome

The inventory domain now exposes a provenance-complete closing-authority contract. A physical observation carries closed evidence roles and content digests; a decision binds the exact observation and reviewer provenance; prior continuity binds the immediately preceding authoritative closing; and the resolution retains every contributing fingerprint and any valuation conflict. Both physical-selected and movement-selected decisions fail closed when their decision predates the named observation.

Focused verification completed with 50 passing inventory-domain tests, clean Ruff and type-checker runs, and an independent formal review reporting zero findings at every severity.

The S167 grounding pass exposed that the first S166 contract had no canonical persistence slot. S166 was reopened and amended: `InventoryClosingAuthorityRecord` is now the sole ledger-owned bundle, its fingerprint binds all nested provenance, and schema version 3 refuses both version 2 and a missing authority slot. The amended gate completed with 53 passing domain tests, clean Ruff and type-checker runs, and a second independent review reporting zero findings.

## Notes

S167 must remove or strictly refuse the still-present CLI `InventoryLedgerPayload.closing_stock` input shape while propagating the new physical-closing authority and continuity evidence through secure ingress. S166 intentionally does not expand into that application and CLI ownership. Projection composition remains assigned to S168.
