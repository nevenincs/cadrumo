---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S14'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---




# Adjudicate Modelo 369 export while preserving Union, Importacion, and Exterior revision separation

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/369/`
- `.vault/reference/`

## Description

Confirm the three separate Modelo 369 registry revisions each apply from
`2021-07-01`: `esquema-union` (quarterly `1T`-`4T`), `esquema-importacion`
(monthly), and `esquema-exterior` (quarterly `EXT-1T`-`EXT-4T`), each with its
own `orden_aplicabilidad = "orden-hac-610-2021:art-1"`. Each revision also
shares an article-2 legal reference, but that reference is not the
applicability selector.
Confirm the single reviewed `aeat-dr-369-2021` XLSX record design in
`src/cadrumo/_data/registry/aeat/legal/iva.toml` applies from `2021-07-01`
with an open end and treat it as one authority shared across the three
regime variants, not as grounds to flatten them into one schema.

Inspect the accepted ADR, research, reference register, and plan. None
contains an accepted decision or explicit current product goal for Modelo
369 machine-file generation; legacy discovery and export-routing wording
only identify a possible outbound surface, a conditional pointer.

Inspect each Modelo 369 revision and the generic export engine. None of the
three revisions has `export_layouts` data. The shared `resolve_export_layout`
and `export_draft` paths remain canonical and fail closed per revision. No
real Modelo 369 golden outbound payload or mutation-sensitive round trip
exists for any of the three regimes.

## Outcome

### `modelo-369-outbound-union-2021-open` | `mandate-gated`

- **Candidate:** Modelo 369 Esquema Union outbound fichero generation for
  quarterly filings from `2021-07-01` with an open end.
- **Mandate:** `conditional`. Legacy discovery identifies a possible outbound
  surface; no accepted decision or explicit product goal confirms it.
- **Exact authority window:** `aeat-dr-369-2021` is a reviewed AEAT XLSX
  record design registered from `2021-07-01` with an open end and covers
  this candidate window.
- **Canonical implementation state:** `gap` only in optional layout data; the
  canonical generic resolver, renderer, and parser are delivered and refuse
  the absent layout for this revision.
- **Real evidence or specimen:** `missing`; no real golden payload exists.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm an explicit current product decision naming
  Esquema Union specifically before authoring any registry layout data for
  this revision.

### `modelo-369-outbound-importacion-2021-open` | `mandate-gated`

- **Candidate:** Modelo 369 Esquema Importacion (IOSS) outbound fichero
  generation for monthly filings from `2021-07-01` with an open end.
- **Mandate:** `conditional`, same reasoning as Esquema Union; not
  independently proven for this distinct regime variant.
- **Exact authority window:** `aeat-dr-369-2021` covers this candidate
  window exactly, shared with the other two regime variants.
- **Canonical implementation state:** `gap` only in optional layout data for
  this specific revision.
- **Real evidence or specimen:** `missing`; no real golden payload exists.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm an explicit current product decision naming
  Esquema Importacion specifically; never assume a Union mandate decision
  covers this distinct regime revision.

### `modelo-369-outbound-exterior-2021-open` | `mandate-gated`

- **Candidate:** Modelo 369 Esquema Exterior outbound fichero generation for
  quarterly filings from `2021-07-01` with an open end.
- **Mandate:** `conditional`, same reasoning as the other two variants; not
  independently proven for this distinct regime variant.
- **Exact authority window:** `aeat-dr-369-2021` covers this candidate
  window exactly, shared with the other two regime variants.
- **Canonical implementation state:** `gap` only in optional layout data for
  this specific revision.
- **Real evidence or specimen:** `missing`; no real golden payload exists.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm an explicit current product decision naming
  Esquema Exterior specifically; never assume a Union or Importacion mandate
  decision covers this distinct regime revision.

## Notes

- Independent Terra high review corrected the description's applicability
  citation: all three revisions select article 1; article 2 is a shared legal
  reference and does not define `orden_aplicabilidad`.
- Grounding used the accepted adjudication contract, all three Modelo 369
  revision.toml files, the single shared legal source entry, generic
  exporter boundaries, and the existing reference register entry for Modelo
  369.
- A single shared record-design source authorizing three regime variants is
  not grounds to merge them into one candidate record or one schema; each
  regime keeps its own disposition row and, if ever admitted, its own
  registry layout data.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
