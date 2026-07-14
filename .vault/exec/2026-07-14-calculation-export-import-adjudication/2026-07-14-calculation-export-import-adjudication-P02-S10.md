---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S10'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---




# Adjudicate Modelo 322 export only for the 2026-and-following authority window and gate earlier revisions

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/322/`
- `.vault/reference/`

## Description

Confirm that the current `2008-y-siguientes` registry revision in
`src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-y-siguientes/revision.toml`
uses `valid_from = 2008-01-01` with the monthly period selector. Confirm that
the reviewed `aeat-dr-322-2026` XLSX record design in
`src/cadrumo/_data/registry/aeat/legal/iva.toml` applies from `2026-01-01`
with an open end. Keep 2008-2025 outside that machine-file authority window.

Inspect the accepted ADR, research, reference register, and plan. None
establishes an accepted decision or explicit current product goal for Modelo
322 machine-file generation; the legacy goal only asks for export/file layout
support "where required," which is a conditional pointer, not a mandate.

Inspect the Modelo 322 registry and the generic export engine. The revision
has no `export_layouts` data. The shared `resolve_export_layout` and
`export_draft` paths remain canonical and fail closed when no layout is
exposed. No real Modelo 322 golden outbound payload or mutation-sensitive
export/parse round trip exists; the mutation-sensitive fichero-BOE suite
covers Modelos 130, 303, and 390 only.

## Outcome

### `modelo-322-outbound-2026-open` | `mandate-gated`

- **Candidate:** Modelo 322 outbound fichero generation for monthly filings
  from `2026-01-01` with an open end under revision `2008-y-siguientes`.
- **Mandate:** `conditional`. The legacy goal names Modelo 322 export/file
  layout support only "where required" and no accepted decision or explicit
  current product goal confirms that requirement yet. The registered record
  design, filing link, and parity reference are not a mandate.
- **Exact authority window:** `aeat-dr-322-2026` is a reviewed AEAT XLSX
  record design registered from `2026-01-01` with an open end and covers this
  candidate window exactly.
- **Canonical implementation state:** `gap` only in optional Modelo 322
  layout data: no export layout is registered. The canonical generic
  resolver, renderer, and parser are delivered and refuse the absent layout.
- **Real evidence or specimen:** `missing`. The reviewed 2026 record-design
  XLSX is available as authority, but no real Modelo 322 golden outbound
  payload or mutation-sensitive round trip exists.
- **Retirement:** `false`.
- **Evidence block:** `true`; a real Modelo 322 golden outbound payload is
  unavailable. Taxonomy precedence selects `mandate-gated` before any
  evidence-gated state because the mandate is unresolved, not merely
  unevidenced.
- **Four-condition gate:** `mandate_met = false`, `exact_authority_met = true`,
  `canonical_gap_met = false`, `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm an explicit current product decision for Modelo
  322 outbound machine-file generation before authoring any registry layout,
  renderer, parser, or golden test.

### `modelo-322-outbound-2008-2025` | `mandate-gated`

- **Candidate:** Modelo 322 outbound fichero generation for filing years
  2008-2025 under revision `2008-y-siguientes`.
- **Mandate:** `conditional`, for the same reason as the 2026-open window;
  not independently proven for this historical span either. Taxonomy
  precedence selects `mandate-gated` ahead of any authority finding.
- **Exact authority window:** `missing`. `aeat-dr-322-2026` starts on
  `2026-01-01` and does not cover 2008-2025; no other registered record
  design exists for this span. Even a future mandate decision could not
  admit this window without exact-window authority.
- **Canonical implementation state:** `gap` only in optional historical
  layout data; the delivered generic resolver, renderer, and parser fail
  closed with no registered layout.
- **Real evidence or specimen:** `missing`; no exact-window official record
  design and no real Modelo 322 golden outbound payload exist for 2008-2025.
- **Retirement:** `false`.
- **Evidence block:** `true`; exact-window evidence is unavailable in
  addition to the unresolved mandate.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`,
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** confirm the product decision named above; never seek or
  extrapolate 2008-2025 record-design authority from the 2026 XLSX in the
  meantime.

## Notes

- Grounding used the accepted adjudication contract, exact Modelo 322
  registry/legal files, generic exporter boundaries, and the existing
  reference register entry for Modelo 322.
- No production source, test, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
