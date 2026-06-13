---
tags:
  - "#reference"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-29-inventory-management-research]]"
  - "[[2026-04-29-inventory-management-adr]]"
  - "[[2026-04-30-inventory-management-hardening-plan]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-04-25-error-code-registry-adr]]"
---

# Inventory and Amortization CLI Design Contract

## Purpose and decision

The current `aeat profile assets` and `aeat profile inventory` commands are compatible with the prototype only. They are useful scaffolding, but they are not the future canonical Kent-facing user experience.

The hardened target is a Kent-facing data ledger surface rooted at `aeat data ledgers ...`. This target treats assets, inventory movements, amortization, Anexo D preview data, migration, and diagnostics as local financial evidence.

The CLI should read as a guided local bookkeeping workflow. It should not read as a low-level profile storage editor. After `aeat data ledgers ...` exists, the public `profile` ledger commands should be removed from the Kent-facing CLI instead of retained as forwarding commands.

## Prerequisites and setup boundaries

This reference assumes an existing AEAT CLI installation and a configured local profile.

Current v1 persistence writes schema-versioned plaintext JSON under `~/.config/aeat`. The hardened target is encrypted storage for financial ledgers, governed by #216, plus migration from plaintext stores.

Ledger commands are local-only. They must not imply live AEAT submission or live AEAT mutation.

User-facing help should point to the getting-started guide for setup, the security runbook for storage, and `aeat doctor` for local diagnostics.

## Glossary

Kent: The representative CLI user. Kent-facing language is plain, task-oriented, and avoids implementation-first phrasing.

Actividad económica: The economic activity that assets, stock movements, and Anexo D values are allocated to.

Anexo D: The Modelo 100 activity annex where ledger values can preview selected actividad económica inputs.

Casilla `0155`: Inventory or stock variation.

Casilla `0173`: Fixed-asset amortization.

Existencias: Inventory or stock held for the activity.

Inmovilizado: Long-lived business assets subject to amortization rules.

IVA soportado: VAT paid on a purchase invoice.

IVA deducible: The deductible portion of VAT paid.

FIFO: First-in, first-out inventory valuation.

PMP: Precio medio ponderado, weighted average inventory valuation.

Coste medio: Average-cost valuation when the ledger type supports it.

LIFO refusal: LIFO must be refused rather than approximated.

JSON envelope: The shared structured output wrapper used by commands that support machine-readable output.

Preview/apply: A mutation model where Kent sees calculated effects before persistence.

## Design norms

The ledger CLI inherits these norms from prior CLI artifacts:

- Kent-first command names, flags, and messages
- Stage-oriented grouping that follows the user workflow
- Local-only behavior by default
- Preview/apply semantics for mutations
- Registered error output using the shared error-code registry
- Shared JSON envelope for commands that support machine-readable output
- Trilingual message scope for Spanish, English, and Hungarian
- Profile banners that disclose the active local profile context
- ASCII-safe terminal copy
- Clear stdout and stderr separation

Human stdout carries successful tables, summaries, and previews. Stderr carries diagnostics, warnings, progress, and registered errors except for JSON commands, where diagnostics and errors are included in the envelope.

## Proposed command map

The following command map is future syntax. It is not the current shipped CLI.

Canonical root:

```text
aeat data ledgers ...
```

Asset ledger commands:

```text
aeat data ledgers assets add
aeat data ledgers assets list
aeat data ledgers assets show
aeat data ledgers assets preview
aeat data ledgers assets schedule
aeat data ledgers assets correct
aeat data ledgers assets dispose
aeat data ledgers assets classes search
aeat data ledgers assets classes list
aeat data ledgers assets amortization preview
aeat data ledgers assets amortization apply
```

Inventory ledger commands:

```text
aeat data ledgers inventory create
aeat data ledgers inventory list
aeat data ledgers inventory show
aeat data ledgers inventory movement add
aeat data ledgers inventory movement correct
aeat data ledgers inventory count close
aeat data ledgers inventory valuation preview
aeat data ledgers inventory valuation apply
aeat data ledgers inventory layers show
```

Anexo D preview:

```text
aeat data ledgers anexo-d preview --modelo 100 --year YYYY --actividad ID
```

Plaintext migration:

```text
aeat data ledgers migrate plaintext --preview
aeat data ledgers migrate plaintext --apply
```

Diagnostics:

```text
aeat doctor ledgers
```

Current prototype commands:

```text
aeat profile assets ...
aeat profile inventory ...
```

Current profile commands remain implementation scaffolding until the canonical tree exists.
The hardened implementation should not keep public forwarding commands for these prototype paths. Removing the old public paths keeps the CLI lean and avoids two ways to perform the same ledger task.

## Asset workflow reference

Asset entry starts from invoice-line data. The hardened add flow should collect or validate:

- Invoice identifier or source reference
- Asset description
- Activity allocation
- Acquisition date
- Base amount
- VAT rate: `0`, `4`, `10`, or `21`
- VAT amount
- Gross amount
- Deductible VAT share
- Useful-life class
- Amortization start date
- Governed libertad reason and citation when special treatment is claimed

The CLI must validate base, VAT, and gross consistency. It must validate useful-life input against the supported LIS table or require a governed exception path.

Mutations must support preview/apply. Duplicate asset identifiers, duplicate invoice-line fingerprints, and repeated amortization postings must be protected.

Future syntax example:

```text
aeat data ledgers assets add --actividad act-retail --asset-id laptop-2026-001 --description "shop laptop" --date 2026-02-10 --base 1200.00 --vat-rate 21 --vat 252.00 --gross 1452.00 --deductible-vat-share 100 --class computer-equipment --preview
```

```text
aeat data ledgers assets add --actividad act-retail --asset-id laptop-2026-001 --description "shop laptop" --date 2026-02-10 --base 1200.00 --vat-rate 21 --vat 252.00 --gross 1452.00 --deductible-vat-share 100 --class computer-equipment --apply
```

Corrections and disposals must be explicit ledger events. They must preserve source trace instead of silently rewriting historical records.

## Inventory workflow reference

Inventory setup is scoped per activity and year. It should declare the valuation method, opening layers where needed, and the operating year.

Target movement families:

- Purchase
- Sale or COGS
- Return
- Correction

Target valuation methods:

- FIFO
- PMP
- Coste medio where supported

Current v1 accepts method labels but does not implement true FIFO or PMP stock layers. The hardened design must implement real layers before those labels are calculation claims.

LIFO must be hard-refused. The command must not approximate LIFO through reversed FIFO or any local workaround.

Negative stock must be refused in the hardened target. The refusal should identify the item, activity, year, attempted movement, and available quantity.

Future syntax examples:

```text
aeat data ledgers inventory create --actividad act-retail --year 2026 --method fifo --preview
```

```text
aeat data ledgers inventory movement add --actividad act-retail --year 2026 --sku notebook-a5 --type purchase --date 2026-01-12 --quantity 100 --unit-cost 2.40 --preview
```

```text
aeat data ledgers inventory valuation preview --actividad act-retail --year 2026
```

## Year-end and Anexo D preview reference

Year-end amortization should support batch processing with truthful idempotency states.

Future syntax:

```text
aeat data ledgers assets amortization preview --actividad act-retail --year 2026
aeat data ledgers assets amortization apply --actividad act-retail --year 2026
```

Each asset result must report one of:

- `created`
- `already_recorded`
- `basis_exhausted`
- `refused`

Anexo D preview must show casilla `0155` for inventory variation and casilla `0173` for amortization when relevant ledger data is supplied and validated.

```text
aeat data ledgers anexo-d preview --modelo 100 --year 2026 --actividad act-retail
```

Ledger values win over manual values only when ledger data is supplied, validated, and explicitly selected by the preview workflow. Missing-ledger fallback must be visible. The CLI must not replace manual Anexo D values with partial or invalid ledger data.

## Output, errors, localization, and security

Human output should use compact tables and short summaries.

Commands that opt into `--json` and are registered must use the shared JSON envelope. New ledger commands must be registered and tested before documentation claims JSON support.

Field-level validation errors must name the failing field and show the accepted range or expected format. Examples include VAT rates outside `0`, `4`, `10`, and `21`, inconsistent gross totals, unsupported valuation methods, duplicate IDs, and negative stock.

Duplicate protection is required for asset IDs, invoice-line fingerprints, movement IDs, and year-end posting attempts.

Plaintext migration must refuse unsafe apply behavior unless Kent explicitly chooses the migration apply command and encrypted persistence is available. The CLI must disclose encrypted local persistence in user-facing output.

Localization scope covers Spanish, English, and Hungarian. Maintainers should keep messages compact and aligned across the three languages.

## Kent roleplay matrix summary

The Kent roleplay matrix must preserve broad behavioral coverage across these scenario families:

- VAT rates at `0`, `4`, `10`, and `21`
- Multi-year asset purchases and amortization schedules
- Shared assets allocated across activities
- Multiple activities in one configured local profile
- Purchase returns and sales returns
- Corrections to invoices, assets, movements, and counts
- Invalid input for amounts, dates, VAT rates, classes, and activity IDs
- LIFO valuation requests
- Negative-stock attempts
- Duplicate asset IDs, movement IDs, and invoice-line references
- Plaintext profile storage detection and migration
- JSON automation for previews, refusals, and successful applies

The roleplay matrix should test real behavior. It must not rely on tautological assertions or fake success paths.

## Help paths

Command help should direct users to:

- The getting-started guide for profile setup
- The JSON output contract for automation
- The security runbook for encrypted local persistence and plaintext migration
- The generated error-code reference for registered refusals
- The inventory concept document for FIFO, PMP, and coste medio terminology
- GitHub issue reporting for defects and unclear tax behavior
- `aeat doctor ledgers` for local ledger diagnostics after that command exists

## Acceptance gates

A hardened implementation is acceptable when:

- Canonical help centers on `aeat data ledgers ...`
- Current profile commands are removed from the public Kent-facing CLI after the canonical tree lands
- Mutations use preview/apply
- Asset entry validates VAT, gross/base consistency, useful-life class, activity allocation, duplicate identity, and governed libertad claims
- Inventory setup and movements validate method, quantities, layers, and negative-stock conditions
- LIFO is refused with a registered error
- Year-end amortization is idempotent and truthful
- Anexo D preview shows casillas `0155` and `0173` with explicit source trace
- Missing-ledger fallback is visible
- Advertised JSON output uses the shared envelope
- Human output keeps stdout and stderr separated
- Messages are available in Spanish, English, and Hungarian within the supported scope
- Encrypted local persistence is disclosed
- Plaintext migration refuses unsafe behavior
- `aeat doctor ledgers` reports ledger readiness, persistence state, and actionable diagnostics

## Non-goals

These commands do not submit data to AEAT.

These commands do not replace professional tax judgment.

These commands do not implement unsupported valuation methods.

These commands do not silently infer Anexo D values from incomplete or invalid ledgers.

These commands do not make profile storage editing the primary user experience.

These commands do not accept manual rewrites of historical ledger facts where a correction, disposal, return, or count reconciliation event is required.
